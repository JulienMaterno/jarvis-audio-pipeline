"""
Jarvis Whisper on Modal - Serverless GPU Transcription

Uses HuggingFace Transformers pipeline (officially supported by Modal)
with pyannote.audio for speaker diarization.

Deploy: python -m modal deploy modal_whisperx.py
Test:   python -m modal run modal_whisperx.py --audio-path test.mp3

Cost: ~$0.05-0.10 per transcription (T4 GPU)
"""

import modal
import os

# Create Modal app
app = modal.App("jarvis-whisperx")

# Model cache volume for faster cold starts
model_cache = modal.Volume.from_name("whisper-model-cache", create_if_missing=True)
MODEL_DIR = "/model-cache"

# Image with HuggingFace Transformers + pyannote (Modal's recommended approach)
whisper_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        # Core dependencies - these work with Modal's CUDA setup
        "torch==2.5.1",
        "transformers==4.47.1",
        "accelerate==1.2.1",
        "huggingface-hub==0.27.0",
        # Audio processing
        "librosa==0.10.2",
        "soundfile==0.12.1",
        "pydub==0.25.1",
        # Speaker diarization
        "pyannote.audio==3.3.2",
        # API
        "fastapi[standard]",
        "numpy<2.0",
    )
    .env({"HF_HUB_CACHE": MODEL_DIR})
)


@app.function(
    image=whisper_image,
    gpu="T4",  # Good enough for Whisper, cheapest option
    timeout=3600,
    volumes={MODEL_DIR: model_cache},
    secrets=[modal.Secret.from_name("huggingface-token")],
)
def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.mp3",
    model_name: str = "openai/whisper-large-v3",
    language: str = None,
    enable_diarization: bool = True,
) -> dict:
    """
    Transcribe audio with Whisper + pyannote diarization on GPU.
    
    Uses HuggingFace Transformers pipeline (Modal's recommended approach).
    
    Args:
        audio_bytes: Raw audio file bytes
        filename: Original filename (for format detection)
        model_name: Whisper model (openai/whisper-tiny, base, small, medium, large-v2, large-v3)
        language: Language code or None for auto-detect
        enable_diarization: Enable speaker diarization
    
    Returns:
        Dict with text, segments, language, duration, speakers
    """
    import tempfile
    import time
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    import librosa
    
    start_time = time.time()
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if device == "cuda" else torch.float32
    
    print(f"Device: {device.upper()}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    
    # Write audio to temp file
    suffix = "." + filename.split(".")[-1] if "." in filename else ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        temp_audio_path = f.name
    
    # Convert to WAV for better compatibility (handles m4a, mp3, etc.)
    wav_path = temp_audio_path.rsplit(".", 1)[0] + ".wav"
    try:
        from pydub import AudioSegment
        print(f"Converting {suffix} to WAV...")
        audio_segment = AudioSegment.from_file(temp_audio_path)
        audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
        audio_segment.export(wav_path, format="wav")
        audio_path = wav_path
        print("Conversion complete.")
    except Exception as e:
        print(f"Pydub conversion failed ({e}), using original file...")
        audio_path = temp_audio_path
        wav_path = None
    
    try:
        # Load audio for duration calculation
        audio_array, sr = librosa.load(audio_path, sr=16000)
        duration = len(audio_array) / sr
        print(f"Audio duration: {duration:.1f}s")
        
        # Step 1: Load Whisper model
        print(f"Step 1/3: Loading model {model_name}...")
        processor = AutoProcessor.from_pretrained(model_name)
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        ).to(device)
        
        # Create transcription pipeline
        pipe = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            torch_dtype=torch_dtype,
            device=device,
        )
        
        # Step 2: Transcribe
        print("Step 2/3: Transcribing...")
        
        # Configure generation
        generate_kwargs = {
            "task": "transcribe",
            "return_timestamps": True,
        }
        if language:
            generate_kwargs["language"] = language
        
        result = pipe(
            audio_path,
            generate_kwargs=generate_kwargs,
            chunk_length_s=30,
            batch_size=8,
        )
        
        # Extract text and chunks
        full_text = result["text"]
        chunks = result.get("chunks", [])
        
        # Build segments from chunks
        segments_list = []
        for chunk in chunks:
            timestamp = chunk.get("timestamp", (0, 0))
            segments_list.append({
                "start": timestamp[0] if timestamp[0] is not None else 0,
                "end": timestamp[1] if timestamp[1] is not None else 0,
                "text": chunk.get("text", "").strip(),
                "speaker": "Unknown"
            })
        
        # If no chunks, create single segment
        if not segments_list:
            segments_list = [{
                "start": 0,
                "end": duration,
                "text": full_text.strip(),
                "speaker": "Unknown"
            }]
        
        detected_language = "unknown"  # Transformers pipeline doesn't expose this easily
        print(f"Transcribed {len(segments_list)} segments")
        
        # Free GPU memory before diarization
        del model, pipe
        torch.cuda.empty_cache()
        
        # Step 3: Speaker diarization
        speakers = []
        if enable_diarization and segments_list:
            hf_token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
            if hf_token:
                print("Step 3/3: Speaker diarization...")
                try:
                    from pyannote.audio import Pipeline as DiarizePipeline
                    
                    # Load diarization pipeline
                    diarize_pipeline = DiarizePipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        use_auth_token=hf_token
                    )
                    diarize_pipeline.to(torch.device(device))
                    
                    # Run diarization
                    diarization = diarize_pipeline(audio_path)
                    
                    # Match speakers to segments by timestamp overlap
                    for seg in segments_list:
                        seg_start = seg["start"]
                        seg_end = seg["end"]
                        seg_mid = (seg_start + seg_end) / 2
                        
                        # Find speaker at segment midpoint
                        for turn, _, speaker in diarization.itertracks(yield_label=True):
                            if turn.start <= seg_mid <= turn.end:
                                seg["speaker"] = speaker
                                break
                    
                    # Get unique speakers
                    speakers = list(set(seg["speaker"] for seg in segments_list if seg["speaker"] != "Unknown"))
                    print(f"Found {len(speakers)} speaker(s): {speakers}")
                    
                except Exception as e:
                    print(f"Diarization failed: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("Step 3/3: Skipping diarization (no HF token)")
        else:
            print("Step 3/3: Skipping diarization (disabled)")
        
        processing_time = time.time() - start_time
        speed = duration / processing_time if processing_time > 0 else 0
        
        print(f"✓ Complete: {duration:.1f}s audio in {processing_time:.1f}s ({speed:.1f}x realtime)")
        
        # Commit model cache
        model_cache.commit()
        
        return {
            "text": full_text.strip(),
            "segments": segments_list,
            "language": detected_language,
            "duration": duration,
            "speakers": speakers,
            "model": model_name,
            "processing_time": processing_time,
        }
        
    finally:
        # Clean up temp files
        if os.path.exists(temp_audio_path):
            os.unlink(temp_audio_path)
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)


@app.function(
    image=whisper_image,
    gpu="T4",
    timeout=120,
    volumes={MODEL_DIR: model_cache},
)
def health_check() -> dict:
    """Check if GPU and dependencies are working."""
    import torch
    
    result = {
        "status": "healthy",
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1) if torch.cuda.is_available() else None,
        "torch_version": torch.__version__,
    }
    
    # Test transformers import
    try:
        from transformers import pipeline
        result["transformers"] = "ok"
    except Exception as e:
        result["transformers"] = str(e)
    
    # Test pyannote import
    try:
        from pyannote.audio import Pipeline
        result["pyannote"] = "ok"
    except Exception as e:
        result["pyannote"] = str(e)
    
    return result


@app.function(
    image=whisper_image,
    gpu="T4",
    timeout=300,
    volumes={MODEL_DIR: model_cache},
)
def download_models():
    """Pre-download models to cache volume for faster cold starts."""
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    import os
    
    print("Downloading Whisper large-v3...")
    processor = AutoProcessor.from_pretrained("openai/whisper-large-v3")
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        "openai/whisper-large-v3",
        torch_dtype="auto",
        low_cpu_mem_usage=True,
        use_safetensors=True,
    )
    del model, processor
    
    # Download diarization model if HF token available
    hf_token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
    if hf_token:
        print("Downloading pyannote diarization model...")
        try:
            from pyannote.audio import Pipeline
            Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
        except Exception as e:
            print(f"Diarization model download failed: {e}")
    
    model_cache.commit()
    print("✓ Models cached!")
    return {"status": "models downloaded"}


# Web endpoint for HTTP access
@app.function(
    image=whisper_image,
    gpu="T4",
    timeout=3600,
    volumes={MODEL_DIR: model_cache},
    secrets=[modal.Secret.from_name("huggingface-token")],
)
@modal.fastapi_endpoint(method="POST")
def transcribe_endpoint(item: dict) -> dict:
    """
    HTTP endpoint for transcription.
    
    POST with JSON: {"audio_base64": "...", "filename": "audio.mp3"}
    """
    import base64
    
    audio_base64 = item.get("audio_base64")
    if not audio_base64:
        return {"error": "Missing audio_base64"}
    
    audio_bytes = base64.b64decode(audio_base64)
    filename = item.get("filename", "audio.mp3")
    language = item.get("language")
    enable_diarization = item.get("enable_diarization", True)
    model_name = item.get("model", "openai/whisper-large-v3")
    
    return transcribe_audio.local(
        audio_bytes=audio_bytes,
        filename=filename,
        model_name=model_name,
        language=language,
        enable_diarization=enable_diarization,
    )


# CLI for testing
@app.local_entrypoint()
def main(audio_path: str = None, test: bool = False, download: bool = False):
    """
    Test transcription from command line.
    
    Usage:
        modal run modal_whisperx.py --audio-path recording.mp3
        modal run modal_whisperx.py --test
        modal run modal_whisperx.py --download  # Pre-cache models
    """
    if test:
        print("Running health check...")
        result = health_check.remote()
        print(f"Health: {result}")
        return
    
    if download:
        print("Downloading models to cache...")
        result = download_models.remote()
        print(f"Result: {result}")
        return
    
    if not audio_path:
        print("Usage: modal run modal_whisperx.py --audio-path <file.mp3>")
        print("       modal run modal_whisperx.py --test")
        print("       modal run modal_whisperx.py --download")
        return
    
    print(f"Reading {audio_path}...")
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    
    print(f"Sending to Modal ({len(audio_bytes) / 1024 / 1024:.1f} MB)...")
    result = transcribe_audio.remote(
        audio_bytes=audio_bytes,
        filename=audio_path,
    )
    
    print("\n" + "=" * 60)
    print("TRANSCRIPT")
    print("=" * 60)
    print(result["text"])
    print("\n" + "=" * 60)
    print(f"Duration: {result['duration']:.1f}s")
    print(f"Language: {result['language']}")
    print(f"Speakers: {result['speakers']}")
    print(f"Processing time: {result['processing_time']:.1f}s")
    print(f"Speed: {result['duration']/result['processing_time']:.1f}x realtime")
