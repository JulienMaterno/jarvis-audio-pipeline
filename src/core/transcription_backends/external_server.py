"""
External GPU Server - Run this on your laptop/workstation with NVIDIA GPU.

This is a FastAPI server that exposes WhisperX transcription as an HTTP API.
Run it on any machine with a GPU, then point Jarvis to it.

Usage:
    # On GPU laptop/workstation:
    cd /path/to/Jarvis
    pip install whisperx fastapi uvicorn python-multipart
    python -m src.core.transcription_backends.external_server --port 8000
    
    # On Airflow server, set:
    EXTERNAL_GPU_URL=http://laptop-ip:8000
    
Security:
    - For local network only: --host 127.0.0.1
    - For remote access: Use VPN or SSH tunnel
    - Optional: Set --api-key for authentication
    
Endpoints:
    GET  /health     - Health check
    GET  /info       - Server info (GPU, model, etc.)
    POST /transcribe - Transcribe audio file
"""

import argparse
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import torch

# FastAPI and dependencies
try:
    from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, Header
    from fastapi.responses import JSONResponse
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not installed. Run: pip install fastapi uvicorn python-multipart")

# WhisperX
try:
    import whisperx
    WHISPERX_AVAILABLE = True
except ImportError:
    WHISPERX_AVAILABLE = False
    print("WhisperX not installed. Run: pip install whisperx")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('WhisperX.Server')


# Global state
app = FastAPI(
    title="WhisperX GPU Server",
    description="GPU-accelerated transcription with speaker diarization",
    version="1.0.0"
)
model = None
model_name = "large-v3"
device = None
hf_token = None
api_key = None


def verify_api_key(authorization: Optional[str] = Header(None)):
    """Verify API key if configured."""
    global api_key
    if api_key:
        if not authorization:
            raise HTTPException(status_code=401, detail="API key required")
        if authorization != f"Bearer {api_key}":
            raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@app.on_event("startup")
async def startup():
    """Load WhisperX model on server start."""
    global model, device
    
    if not WHISPERX_AVAILABLE:
        logger.error("WhisperX not available!")
        return
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    
    logger.info(f"Loading WhisperX model: {model_name}")
    logger.info(f"Device: {device.upper()} ({compute_type})")
    
    if device == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        logger.info(f"GPU: {gpu_name} ({gpu_mem:.1f} GB)")
    
    model = whisperx.load_model(model_name, device, compute_type=compute_type)
    logger.info("✓ Model loaded and ready")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "model_loaded": model is not None}


@app.get("/info")
async def info():
    """Get server information."""
    info_dict = {
        "model": model_name,
        "device": device,
        "model_loaded": model is not None,
        "diarization_enabled": hf_token is not None,
    }
    
    if device == "cuda" and torch.cuda.is_available():
        info_dict["gpu"] = {
            "name": torch.cuda.get_device_name(0),
            "memory_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1),
            "memory_used_gb": round(torch.cuda.memory_allocated(0) / 1e9, 2),
        }
    
    return info_dict


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form(default=""),
    enable_diarization: str = Form(default="true"),
    _: bool = Depends(verify_api_key),
):
    """
    Transcribe an audio file.
    
    Args:
        file: Audio file (mp3, wav, m4a, etc.)
        language: Language code or empty for auto-detect
        enable_diarization: Enable speaker diarization (true/false)
    
    Returns:
        Transcription result with text, segments, speakers, etc.
    """
    global model, device, hf_token
    
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    start_time = time.time()
    
    # Parse parameters
    lang = language if language else None
    diarize = enable_diarization.lower() == "true"
    
    logger.info(f"Transcribing: {file.filename} (diarization={diarize})")
    
    # Save uploaded file temporarily
    suffix = Path(file.filename).suffix or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        audio_path = tmp.name
    
    try:
        # Load audio
        audio = whisperx.load_audio(audio_path)
        
        # Transcribe
        logger.info("Step 1/4: Transcribing...")
        result = model.transcribe(
            audio,
            batch_size=16 if device == "cuda" else 4,
            language=lang
        )
        detected_language = result.get('language', lang or 'en')
        
        # Align timestamps
        logger.info("Step 2/4: Aligning timestamps...")
        model_a, metadata = whisperx.load_align_model(
            language_code=detected_language,
            device=device
        )
        result = whisperx.align(
            result["segments"],
            model_a,
            metadata,
            audio,
            device,
            return_char_alignments=False
        )
        
        # Speaker diarization
        speakers = []
        if diarize and hf_token:
            logger.info("Step 3/4: Identifying speakers...")
            try:
                diarize_model = whisperx.DiarizationPipeline(
                    use_auth_token=hf_token,
                    device=device
                )
                diarize_segments = diarize_model(audio)
                result = whisperx.assign_word_speakers(diarize_segments, result)
                speakers = list(set(
                    seg.get('speaker', 'Unknown')
                    for seg in result["segments"]
                    if 'speaker' in seg
                ))
                logger.info(f"Found {len(speakers)} speaker(s)")
            except Exception as e:
                logger.warning(f"Diarization failed: {e}")
        else:
            logger.info("Step 3/4: Skipping diarization")
        
        # Format output
        logger.info("Step 4/4: Formatting output...")
        segments_list = []
        full_text = []
        
        for segment in result["segments"]:
            segments_list.append({
                'start': segment['start'],
                'end': segment['end'],
                'text': segment['text'].strip(),
                'speaker': segment.get('speaker', 'Unknown')
            })
            full_text.append(segment['text'].strip())
        
        duration = segments_list[-1]['end'] if segments_list else 0
        processing_time = time.time() - start_time
        
        logger.info(f"✓ Complete: {duration:.1f}s audio in {processing_time:.1f}s")
        
        return JSONResponse({
            'text': ' '.join(full_text),
            'segments': segments_list,
            'language': detected_language,
            'duration': duration,
            'speakers': speakers,
            'model': model_name,
            'processing_time': processing_time,
        })
        
    finally:
        # Cleanup temp file
        os.unlink(audio_path)


def main():
    """Run the server."""
    global model_name, hf_token, api_key
    
    parser = argparse.ArgumentParser(description="WhisperX GPU Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--model", default="large-v3", help="Whisper model size")
    parser.add_argument("--hf-token", help="HuggingFace token for diarization")
    parser.add_argument("--api-key", help="API key for authentication")
    args = parser.parse_args()
    
    model_name = args.model
    hf_token = args.hf_token or os.getenv("HUGGINGFACE_TOKEN")
    api_key = args.api_key or os.getenv("EXTERNAL_GPU_API_KEY")
    
    if not FASTAPI_AVAILABLE:
        print("Error: FastAPI required. Install with: pip install fastapi uvicorn python-multipart")
        return 1
    
    if not WHISPERX_AVAILABLE:
        print("Error: WhisperX required. Install with: pip install whisperx")
        return 1
    
    if not torch.cuda.is_available():
        print("Warning: No GPU detected! Transcription will be slow.")
    
    if api_key:
        print(f"API key authentication enabled")
    else:
        print("Warning: No API key - server accessible without authentication")
    
    if hf_token:
        print("Speaker diarization enabled")
    else:
        print("Warning: No HuggingFace token - diarization disabled")
        print("Set HUGGINGFACE_TOKEN or use --hf-token")
    
    print(f"\nStarting server on http://{args.host}:{args.port}")
    print(f"Model: {model_name}")
    print(f"\nEndpoints:")
    print(f"  GET  /health     - Health check")
    print(f"  GET  /info       - Server info")
    print(f"  POST /transcribe - Transcribe audio\n")
    
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
