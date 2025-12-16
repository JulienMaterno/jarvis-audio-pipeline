"""
Local Backend - CPU-based fallback transcription.

Uses the existing WhisperXTranscriber for local CPU transcription.
This is slow but works anywhere without external dependencies.
"""

import logging
import time
from pathlib import Path
from typing import Optional

from .base import (
    TranscriptionBackend,
    TranscriptionResult,
    BackendUnavailableError,
    TranscriptionError
)

logger = logging.getLogger('Jarvis.Transcription.Local')


class LocalBackend(TranscriptionBackend):
    """
    Local CPU-based transcription backend.
    
    Uses WhisperX directly on the local machine.
    Slow on CPU (~10x realtime) but requires no external services.
    """
    
    name = "local"
    
    def __init__(
        self,
        model_name: str = "large-v3",
        enable_diarization: bool = True,
    ):
        self.model_name = model_name
        self.enable_diarization = enable_diarization
        self._transcriber = None
        
    def is_available(self) -> bool:
        """Check if local transcription is available."""
        try:
            import whisperx
            import torch
            return True
        except (ImportError, AttributeError, Exception) as e:
            # Handle import errors including torchaudio version mismatches
            return False
    
    def _get_transcriber(self):
        """Get or create local transcriber instance."""
        if self._transcriber is None:
            from src.core.transcriber import WhisperXTranscriber
            self._transcriber = WhisperXTranscriber(
                model_name=self.model_name,
                enable_diarization=self.enable_diarization
            )
        return self._transcriber
    
    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        enable_diarization: bool = True
    ) -> TranscriptionResult:
        """Transcribe audio locally."""
        if not self.is_available():
            raise BackendUnavailableError("WhisperX not installed locally")
        
        start_time = time.time()
        logger.info(f"Transcribing locally: {audio_path.name}")
        logger.warning("Using local CPU - this may be slow for long audio")
        
        try:
            transcriber = self._get_transcriber()
            result = transcriber.transcribe(audio_path, language=language)
            
            processing_time = time.time() - start_time
            logger.info(f"Local transcription complete in {processing_time:.1f}s")
            
            return TranscriptionResult(
                text=result['text'],
                segments=result['segments'],
                language=result['language'],
                duration=result['duration'],
                speakers=result.get('speakers', []),
                backend="local",
                model=self.model_name,
                processing_time=processing_time,
            )
            
        except Exception as e:
            logger.error(f"Local transcription failed: {e}")
            raise TranscriptionError(f"Local transcription failed: {e}") from e
    
    def get_status(self) -> dict:
        """Get local backend status."""
        import torch
        
        status = {
            'name': self.name,
            'available': self.is_available(),
            'model': self.model_name,
            'device': 'cuda' if torch.cuda.is_available() else 'cpu',
        }
        
        if torch.cuda.is_available():
            status['gpu'] = torch.cuda.get_device_name(0)
        
        return status
