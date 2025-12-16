"""
Modal Backend - GPU transcription via Modal.com

Uses the deployed jarvis-whisperx app for fast GPU transcription.
Supports two modes:
1. Modal SDK (when authenticated locally) - fastest
2. HTTP API (for Docker/containers without Modal auth) - works anywhere

Cost: ~$0.05-0.15 per transcription (T4 GPU)
Speed: ~10-20x realtime for transcription

Setup:
1. Deploy: modal deploy modal_whisperx_v2.py
2. Get the web endpoint URL from Modal dashboard
"""

import logging
import os
import time
import base64
import json
from pathlib import Path
from typing import Optional

from .base import (
    TranscriptionBackend, 
    TranscriptionResult, 
    BackendUnavailableError,
    TranscriptionError
)

logger = logging.getLogger('Jarvis.Transcription.Modal')

# Check if Modal SDK is installed
try:
    import modal
    MODAL_SDK_AVAILABLE = True
except ImportError:
    MODAL_SDK_AVAILABLE = False
    logger.debug("Modal SDK not installed - will use HTTP API")

# Check if requests is available for HTTP fallback
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class ModalBackend(TranscriptionBackend):
    """
    Transcription backend using deployed Modal app.
    
    Uses the pre-deployed jarvis-whisperx app which has:
    - HuggingFace Transformers Whisper (large-v3)
    - Pyannote speaker diarization
    - Optimized for T4 GPU
    
    Supports two modes:
    1. Modal SDK (if authenticated) - uses modal.Cls.from_name()
    2. HTTP API (fallback) - uses the web endpoint
    
    Cost: ~$0.05-0.15 per transcription
    Speed: ~10-20x realtime
    """
    
    name = "modal"
    
    # Modal web endpoint URL (set via env var or use default)
    DEFAULT_ENDPOINT = "https://aaron-j-putting--jarvis-whisperx-transcribe-endpoint.modal.run"
    
    def __init__(
        self,
        model_name: str = "openai/whisper-large-v3",
        gpu_type: str = "T4",
    ):
        self.model_name = model_name
        self.gpu_type = gpu_type
        self._transcriber_cls = None
        self._use_sdk = False
        self._endpoint_url = os.getenv('MODAL_ENDPOINT_URL', self.DEFAULT_ENDPOINT)
    
    def _check_sdk_auth(self) -> bool:
        """Check if Modal SDK is authenticated."""
        if not MODAL_SDK_AVAILABLE:
            return False
        
        # Fix whitespace in Modal tokens from Secret Manager
        token_id = os.getenv('MODAL_TOKEN_ID', '').strip()
        token_secret = os.getenv('MODAL_TOKEN_SECRET', '').strip()
        if token_id and token_secret:
            os.environ['MODAL_TOKEN_ID'] = token_id
            os.environ['MODAL_TOKEN_SECRET'] = token_secret
        
        try:
            from modal.config import Config as ModalConfig
            config = ModalConfig()
            config_dict = config.to_dict()
            return config_dict.get('token_id') is not None
        except Exception:
            return False
    
    def is_available(self) -> bool:
        """Check if Modal is available (SDK or HTTP)."""
        # Check SDK first
        if self._check_sdk_auth():
            self._use_sdk = True
            logger.debug("Modal SDK authenticated - using SDK")
            return True
        
        # Fall back to HTTP endpoint
        if REQUESTS_AVAILABLE and self._endpoint_url:
            self._use_sdk = False
            logger.debug("Using Modal HTTP API endpoint")
            return True
        
        return False
    
    def _get_transcriber(self):
        """Get the deployed WhisperTranscriber class (SDK mode only)."""
        if self._transcriber_cls is not None:
            return self._transcriber_cls
        
        import modal
        
        try:
            self._transcriber_cls = modal.Cls.from_name("jarvis-whisperx", "WhisperTranscriber")
            logger.info("Connected to deployed jarvis-whisperx app")
        except modal.exception.NotFoundError:
            raise BackendUnavailableError(
                "jarvis-whisperx app not deployed. Run: modal deploy modal_whisperx_v2.py"
            )
        
        return self._transcriber_cls
    
    def _transcribe_via_sdk(
        self,
        audio_path: Path,
        language: Optional[str],
        enable_diarization: bool
    ) -> dict:
        """Transcribe using Modal SDK."""
        audio_bytes = audio_path.read_bytes()
        TranscriberCls = self._get_transcriber()
        transcriber = TranscriberCls()
        
        return transcriber.transcribe.remote(
            audio_bytes=audio_bytes,
            filename=audio_path.name,
            language=language,
            enable_diarization=enable_diarization,
        )
    
    def _transcribe_via_http(
        self,
        audio_path: Path,
        language: Optional[str],
        enable_diarization: bool
    ) -> dict:
        """Transcribe using HTTP API endpoint."""
        import requests
        
        audio_bytes = audio_path.read_bytes()
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        payload = {
            "audio_base64": audio_base64,
            "filename": audio_path.name,
            "enable_diarization": enable_diarization,
        }
        if language:
            payload["language"] = language
        
        logger.info(f"Calling Modal HTTP endpoint: {self._endpoint_url}")
        
        response = requests.post(
            self._endpoint_url,
            json=payload,
            timeout=600,  # 10 minute timeout for long audio
        )
        
        if response.status_code != 200:
            raise TranscriptionError(f"Modal API error: {response.status_code} - {response.text}")
        
        return response.json()
    
    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        enable_diarization: bool = True
    ) -> TranscriptionResult:
        """Transcribe audio using deployed Modal app."""
        if not self.is_available():
            raise BackendUnavailableError("Modal is not available")
        
        start_time = time.time()
        file_size_mb = audio_path.stat().st_size / 1024 / 1024
        logger.info(f"Sending {audio_path.name} ({file_size_mb:.1f} MB) to Modal...")
        
        try:
            # Use SDK or HTTP based on availability
            if self._use_sdk:
                logger.debug("Using Modal SDK")
                result = self._transcribe_via_sdk(audio_path, language, enable_diarization)
            else:
                logger.debug("Using Modal HTTP API")
                result = self._transcribe_via_http(audio_path, language, enable_diarization)
            
            processing_time = time.time() - start_time
            
            # Check for errors
            if 'error' in result:
                raise TranscriptionError(f"Modal error: {result['error']}")
            
            # Log results
            duration = result.get('duration', 0)
            speed = duration / processing_time if processing_time > 0 else 0
            mode = "SDK" if self._use_sdk else "HTTP"
            logger.info(f"Modal ({mode}) complete: {duration:.1f}s audio in {processing_time:.1f}s ({speed:.1f}x realtime)")
            
            return TranscriptionResult(
                text=result['text'],
                segments=result.get('segments', []),
                language=result.get('language', 'unknown'),
                duration=duration,
                speakers=result.get('speakers', []),
                backend="modal",
                model=result.get('model', self.model_name),
                processing_time=processing_time,
            )
            
        except BackendUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Modal transcription failed: {e}")
            raise TranscriptionError(f"Modal transcription failed: {e}") from e
    
    def get_status(self) -> dict:
        """Get Modal backend status."""
        available = self.is_available()
        
        deployed = False
        if available and self._use_sdk:
            try:
                self._get_transcriber()
                deployed = True
            except:
                pass
        
        return {
            'name': self.name,
            'available': available,
            'mode': 'sdk' if self._use_sdk else 'http',
            'deployed': deployed,
            'endpoint_url': self._endpoint_url if not self._use_sdk else None,
            'model': self.model_name,
            'gpu': self.gpu_type,
        }
