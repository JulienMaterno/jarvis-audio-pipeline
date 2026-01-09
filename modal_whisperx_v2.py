"""
Jarvis Whisper on Modal - Serverless GPU Transcription (Optimized)

Uses class-based approach to keep models loaded in memory.
Models load ONCE on container start, then stay warm for fast inference.

STEREO CHANNEL SUPPORT:
- Left channel = User's voice (mic)
- Right channel = Other person's voice (loopback/system audio)
- Automatic speaker labeling based on channel

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
        stereo_mode: str = "auto",  # "auto", "separate_channels", "merge"
        left_speaker: str = "Aaron",  # Name for left channel speaker (mic = user)
        right_speaker: str = "Other Person",  # Name for right channel speaker (loopback)
    ) -> dict:
        """
        Transcribe audio with pre-loaded models (FAST!).
        
        Args:
            audio_bytes: Raw audio file bytes
            filename: Original filename (for format detection)
            language: Language code or None for auto-detect
            enable_diarization: Enable speaker diarization (for mono audio)
            stereo_mode: How to handle stereo audio:
                - "auto": Detect stereo, use channels if found
                - "separate_channels": Force channel-based speaker ID
                - "merge": Mix to mono (old behavior)
            left_speaker: Name for left channel (default: "User")
            right_speaker: Name for right channel (default: "Other Person")
        
        Returns:
            Dict with text, segments, language, duration, speakers
        """
        import tempfile
        import time
        import torch
        import librosa
        import numpy as np
        from pydub import AudioSegment
        
        start_time = time.time()
        
        # Write audio to temp file
        suffix = "." + filename.split(".")[-1] if "." in filename else ".mp3"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            temp_audio_path = f.name
        
        wav_path = None
        left_wav = None
        right_wav = None
        
        try:
            # Load audio and check channels
            print(f"Loading audio: {filename}")
            audio_segment = AudioSegment.from_file(temp_audio_path)
            original_channels = audio_segment.channels
            duration = len(audio_segment) / 1000.0  # Duration in seconds
            
            print(f"Audio: {duration:.1f}s, {original_channels} channel(s), {audio_segment.frame_rate}Hz")
            
            # Decide processing mode
            use_stereo_separation = (
                original_channels == 2 and 
                stereo_mode in ("auto", "separate_channels")
            )
            
            if use_stereo_separation:
                print("🎧 STEREO MODE: Separating channels for speaker identification")
                print(f"   Left channel → {left_speaker}")
                print(f"   Right channel → {right_speaker}")
                
                # Split stereo into separate mono channels
                channels = audio_segment.split_to_mono()
                left_channel = channels[0].set_frame_rate(16000)
                right_channel = channels[1].set_frame_rate(16000)
                
                # Check which channels have audio
                left_rms = left_channel.rms
                right_rms = right_channel.rms
                print(f"   Left RMS: {left_rms}, Right RMS: {right_rms}")
                
                # Export channels to temp files
                left_wav = temp_audio_path.rsplit(".", 1)[0] + "_left.wav"
                right_wav = temp_audio_path.rsplit(".", 1)[0] + "_right.wav"
                left_channel.export(left_wav, format="wav")
                right_channel.export(right_wav, format="wav")
                
                # Transcribe each channel
                segments_list = []
                
                # RMS threshold: Use very low threshold (3) to not miss quiet speech
                # Silence is typically RMS ~0-2, even whispered speech is RMS 5+
                # If BOTH channels are below threshold, still try left (user's mic)
                RMS_THRESHOLD = 3
                
                # Determine which channels to transcribe
                transcribe_left = left_rms > RMS_THRESHOLD
                transcribe_right = right_rms > RMS_THRESHOLD
                
                # If neither channel meets threshold but left has any audio, transcribe it anyway
                if not transcribe_left and not transcribe_right and left_rms > 0:
                    print(f"Both channels very quiet (L={left_rms}, R={right_rms}), forcing left channel transcription")
                    transcribe_left = True
                
                # Transcribe left channel (User)
                if transcribe_left:
                    print(f"Transcribing left channel ({left_speaker}), RMS={left_rms}...")
                    left_result = self._transcribe_mono(left_wav, language)
                    for seg in left_result.get("segments", []):
                        seg["speaker"] = left_speaker
                        seg["channel"] = "left"
                        segments_list.append(seg)
                else:
                    print(f"Skipping left channel - no audio (RMS={left_rms})")
                
                # Transcribe right channel (Other Person)
                if transcribe_right:
                    print(f"Transcribing right channel ({right_speaker}), RMS={right_rms}...")
                    right_result = self._transcribe_mono(right_wav, language)
                    for seg in right_result.get("segments", []):
                        seg["speaker"] = right_speaker
                        seg["channel"] = "right"
                        segments_list.append(seg)
                else:
                    print(f"Skipping right channel - no audio (RMS={right_rms})")
                
                # Sort all segments by start time
                segments_list.sort(key=lambda x: x["start"])
                
                # Build full text with speaker labels
                full_text_parts = []
                current_speaker = None
                for seg in segments_list:
                    if seg["speaker"] != current_speaker:
                        current_speaker = seg["speaker"]
                        full_text_parts.append(f"\n[{current_speaker}]: ")
                    full_text_parts.append(seg["text"].strip() + " ")
                
                full_text = "".join(full_text_parts).strip()
                # Build speakers list based on what was actually transcribed
                speakers = []
                if transcribe_left:
                    speakers.append(left_speaker)
                if transcribe_right:
                    speakers.append(right_speaker)
                
                processing_time = time.time() - start_time
                
                return {
                    "text": full_text,
                    "segments": segments_list,
                    "language": "auto",
                    "duration": duration,
                    "speakers": speakers,
                    "model": "openai/whisper-large-v3",
                    "processing_time": processing_time,
                    "stereo_mode": "separate_channels",
                    "channel_mapping": {
                        "left": left_speaker,
                        "right": right_speaker
                    }
                }
            
            else:
                # Standard mono processing (original behavior)
                print("Processing as mono audio...")
                wav_path = temp_audio_path.rsplit(".", 1)[0] + ".wav"
                audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
                audio_segment.export(wav_path, format="wav")
                
                result = self._transcribe_mono(wav_path, language)
                
                # Run diarization on mono audio if enabled
                if enable_diarization and self.diarize_pipeline and result.get("segments"):
                    print("Diarizing...")
                    try:
                        diarization = self.diarize_pipeline(wav_path)
                        for seg in result["segments"]:
                            seg_mid = (seg["start"] + seg["end"]) / 2
                            for turn, _, speaker in diarization.itertracks(yield_label=True):
                                if turn.start <= seg_mid <= turn.end:
                                    seg["speaker"] = speaker
                                    break
                        result["speakers"] = list(set(
                            seg["speaker"] for seg in result["segments"] 
                            if seg.get("speaker") and seg["speaker"] != "Unknown"
                        ))
                    except Exception as e:
                        print(f"Diarization failed: {e}")
                
                result["processing_time"] = time.time() - start_time
                result["stereo_mode"] = "mono"
                return result
                
        finally:
            # Cleanup temp files
            for path in [temp_audio_path, wav_path, left_wav, right_wav]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
    
    def _transcribe_mono(self, audio_path: str, language: str = None) -> dict:
        """Transcribe a mono audio file."""
        import time
        import librosa
        
        # Get duration
        audio_array, sr = librosa.load(audio_path, sr=16000)
        duration = len(audio_array) / sr
        
        # Transcribe
        transcribe_start = time.time()
        
        generate_kwargs = {"task": "transcribe", "return_timestamps": True}
        if language:
            generate_kwargs["language"] = language
        
        result = self.whisper_pipe(
            audio_path,
            generate_kwargs=generate_kwargs,
            chunk_length_s=30,
            batch_size=16,
        )
        
        transcribe_time = time.time() - transcribe_start
        print(f"  Transcribed {duration:.1f}s in {transcribe_time:.1f}s ({duration/transcribe_time:.1f}x realtime)")
        
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
        
        return {
            "text": full_text.strip(),
            "segments": segments_list,
            "language": "auto",
            "duration": duration,
            "speakers": [],
            "model": "openai/whisper-large-v3",
            "transcribe_time": transcribe_time,
        }
    
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
    """
    HTTP endpoint for transcription.
    
    Supports stereo audio with channel-based speaker identification:
    - Left channel = User (from mic)
    - Right channel = Other Person (from system audio/loopback)
    """
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
        stereo_mode=item.get("stereo_mode", "auto"),
        left_speaker=item.get("left_speaker", "Aaron"),
        right_speaker=item.get("right_speaker", "Other Person"),
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
