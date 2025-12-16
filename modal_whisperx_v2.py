"""
Jarvis Whisper on Modal - Serverless GPU Transcription (Optimized)

Uses class-based approach to keep models loaded in memory.
Models load ONCE on container start, then stay warm for fast inference.

Deploy: python -m modal deploy modal_whisperx_v2.py
Test:   python -m modal run modal_whisperx_v2.py --audio-path test.mp3

Speed: ~10-20x realtime on warm container (vs 2-3x with cold start)
"""

import modal
import os

# Create Modal app
app = modal.App("jarvis-whisperx")

# Model cache volume for faster cold starts
model_cache = modal.Volume.from_name("whisper-model-cache", create_if_missing=True)
MODEL_DIR = "/model-cache"

# Image with HuggingFace Transformers + pyannote
whisper_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        # Core dependencies
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


@app.cls(
    image=whisper_image,
    gpu="T4",
    timeout=7200,  # 2 hours - handles very long recordings
    volumes={MODEL_DIR: model_cache},
    secrets=[modal.Secret.from_name("huggingface-token")],
    scaledown_window=300,  # Keep container warm for 5 minutes
)
class WhisperTranscriber:
    """
    Persistent Whisper transcription service.
    
    Models are loaded ONCE when the container starts via @modal.enter().
    Container stays warm for 5 minutes between requests.
    """
    
    @modal.enter()
    def load_models(self):
        """Load models once when container starts."""
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
        
        print("=" * 60)
        print("LOADING MODELS (one-time startup)")
        print("=" * 60)
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if self.device == "cuda" else torch.float32
        
        print(f"Device: {self.device.upper()}")
        if self.device == "cuda":
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        
        # Load Whisper model
        model_name = "openai/whisper-large-v3"
        print(f"Loading Whisper model: {model_name}...")
        
        processor = AutoProcessor.from_pretrained(model_name)
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_name,
            torch_dtype=self.torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        ).to(self.device)
        
        self.whisper_pipe = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            torch_dtype=self.torch_dtype,
            device=self.device,
        )
        print("✓ Whisper loaded")
        
        # Load diarization pipeline
        self.diarize_pipeline = None
        hf_token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
        if hf_token:
            print("Loading pyannote diarization...")
            try:
                from pyannote.audio import Pipeline as DiarizePipeline
                self.diarize_pipeline = DiarizePipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=hf_token
                )
                self.diarize_pipeline.to(torch.device(self.device))
                print("✓ Diarization loaded")
            except Exception as e:
                print(f"⚠ Diarization failed to load: {e}")
        else:
            print("⚠ No HF token - diarization disabled")
        
        # Commit cache
        model_cache.commit()
        print("=" * 60)
        print("MODELS READY - Container is warm!")
        print("=" * 60)
    
    @modal.method()
    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.mp3",
        language: str = None,
        enable_diarization: bool = True,
    ) -> dict:
        """
        Transcribe audio with pre-loaded models (FAST!).
        
        Args:
            audio_bytes: Raw audio file bytes
            filename: Original filename (for format detection)
            language: Language code or None for auto-detect
            enable_diarization: Enable speaker diarization
        
        Returns:
            Dict with text, segments, language, duration, speakers
        """
        import tempfile
        import time
        import torch
        import librosa
        from pydub import AudioSegment
        
        start_time = time.time()
        
        # Write audio to temp file
        suffix = "." + filename.split(".")[-1] if "." in filename else ".mp3"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            temp_audio_path = f.name
        
        # Convert to WAV for compatibility
        wav_path = temp_audio_path.rsplit(".", 1)[0] + ".wav"
        try:
            print(f"Converting {suffix} to WAV...")
            audio_segment = AudioSegment.from_file(temp_audio_path)
            audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
            audio_segment.export(wav_path, format="wav")
            audio_path = wav_path
        except Exception as e:
            print(f"Conversion failed ({e}), using original...")
            audio_path = temp_audio_path
            wav_path = None
        
        try:
            # Get duration
            audio_array, sr = librosa.load(audio_path, sr=16000)
            duration = len(audio_array) / sr
            print(f"Audio: {duration:.1f}s")
            
            # Transcribe (model already loaded!)
            print("Transcribing...")
            transcribe_start = time.time()
            
            generate_kwargs = {"task": "transcribe", "return_timestamps": True}
            if language:
                generate_kwargs["language"] = language
            
            result = self.whisper_pipe(
                audio_path,
                generate_kwargs=generate_kwargs,
                chunk_length_s=30,
                batch_size=16,  # Higher batch size for faster processing
            )
            
            transcribe_time = time.time() - transcribe_start
            print(f"Transcription: {transcribe_time:.1f}s ({duration/transcribe_time:.1f}x realtime)")
            
            # Extract segments
            full_text = result["text"]
            chunks = result.get("chunks", [])
            
            segments_list = []
            for chunk in chunks:
                timestamp = chunk.get("timestamp", (0, 0))
                segments_list.append({
                    "start": timestamp[0] if timestamp[0] is not None else 0,
                    "end": timestamp[1] if timestamp[1] is not None else 0,
                    "text": chunk.get("text", "").strip(),
                    "speaker": "Unknown"
                })
            
            if not segments_list:
                segments_list = [{
                    "start": 0,
                    "end": duration,
                    "text": full_text.strip(),
                    "speaker": "Unknown"
                }]
            
            # Diarization (model already loaded!)
            speakers = []
            if enable_diarization and self.diarize_pipeline and segments_list:
                print("Diarizing...")
                diarize_start = time.time()
                
                try:
                    diarization = self.diarize_pipeline(audio_path)
                    
                    for seg in segments_list:
                        seg_mid = (seg["start"] + seg["end"]) / 2
                        for turn, _, speaker in diarization.itertracks(yield_label=True):
                            if turn.start <= seg_mid <= turn.end:
                                seg["speaker"] = speaker
                                break
                    
                    speakers = list(set(seg["speaker"] for seg in segments_list if seg["speaker"] != "Unknown"))
                    diarize_time = time.time() - diarize_start
                    print(f"Diarization: {diarize_time:.1f}s - {len(speakers)} speaker(s)")
                except Exception as e:
                    print(f"Diarization failed: {e}")
            
            processing_time = time.time() - start_time
            speed = duration / processing_time if processing_time > 0 else 0
            
            print(f"✓ Complete: {duration:.1f}s audio in {processing_time:.1f}s ({speed:.1f}x realtime)")
            
            return {
                "text": full_text.strip(),
                "segments": segments_list,
                "language": "auto",
                "duration": duration,
                "speakers": speakers,
                "model": "openai/whisper-large-v3",
                "processing_time": processing_time,
                "transcribe_time": transcribe_time,
            }
            
        finally:
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)
    
    @modal.method()
    def health(self) -> dict:
        """Check if models are loaded."""
        import torch
        return {
            "status": "healthy",
            "whisper_loaded": self.whisper_pipe is not None,
            "diarization_loaded": self.diarize_pipeline is not None,
            "device": self.device,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }


# Keep the simple function for backward compatibility
@app.function(
    image=whisper_image,
    gpu="T4",
    timeout=3600,
    volumes={MODEL_DIR: model_cache},
    secrets=[modal.Secret.from_name("huggingface-token")],
)
def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.mp3",
    language: str = None,
    enable_diarization: bool = True,
) -> dict:
    """Wrapper that uses the class-based transcriber."""
    transcriber = WhisperTranscriber()
    return transcriber.transcribe.remote(
        audio_bytes=audio_bytes,
        filename=filename,
        language=language,
        enable_diarization=enable_diarization,
    )


# Web endpoint
@app.function(
    image=whisper_image,
    gpu="T4",
    timeout=3600,
    volumes={MODEL_DIR: model_cache},
    secrets=[modal.Secret.from_name("huggingface-token")],
)
@modal.fastapi_endpoint(method="POST")
def transcribe_endpoint(item: dict) -> dict:
    """HTTP endpoint for transcription."""
    import base64
    
    audio_base64 = item.get("audio_base64")
    if not audio_base64:
        return {"error": "Missing audio_base64"}
    
    audio_bytes = base64.b64decode(audio_base64)
    transcriber = WhisperTranscriber()
    return transcriber.transcribe.remote(
        audio_bytes=audio_bytes,
        filename=item.get("filename", "audio.mp3"),
        language=item.get("language"),
        enable_diarization=item.get("enable_diarization", True),
    )


# CLI
@app.local_entrypoint()
def main(audio_path: str = None, test: bool = False):
    """
    Test transcription from command line.
    
    Usage:
        modal run modal_whisperx_v2.py --audio-path recording.mp3
        modal run modal_whisperx_v2.py --test
    """
    transcriber = WhisperTranscriber()
    
    if test:
        print("Running health check...")
        result = transcriber.health.remote()
        print(f"Health: {result}")
        return
    
    if not audio_path:
        print("Usage: modal run modal_whisperx_v2.py --audio-path <file.mp3>")
        print("       modal run modal_whisperx_v2.py --test")
        return
    
    print(f"Reading {audio_path}...")
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    
    print(f"Sending to Modal ({len(audio_bytes) / 1024 / 1024:.1f} MB)...")
    result = transcriber.transcribe.remote(
        audio_bytes=audio_bytes,
        filename=audio_path,
    )
    
    print("\n" + "=" * 60)
    print("TRANSCRIPT")
    print("=" * 60)
    print(result["text"])
    print("\n" + "=" * 60)
    print(f"Duration: {result['duration']:.1f}s")
    print(f"Speakers: {result['speakers']}")
    print(f"Total time: {result['processing_time']:.1f}s")
    print(f"Transcribe only: {result.get('transcribe_time', 0):.1f}s")
    print(f"Speed: {result['duration']/result['processing_time']:.1f}x realtime")
