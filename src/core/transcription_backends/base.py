"""
Base classes for transcription backends.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger('Jarvis.Transcription.Base')


@dataclass
class TranscriptionResult:
    """Standardized transcription result across all backends."""
    text: str
    segments: List[Dict[str, Any]]
    language: str
    duration: float
    speakers: List[str] = field(default_factory=list)
    backend: str = "unknown"
    model: str = "unknown"
    processing_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility with existing code."""
        return {
            'text': self.text,
            'segments': self.segments,
            'language': self.language,
            'duration': self.duration,
            'speakers': self.speakers,
            'backend': self.backend,
            'model': self.model,
            'processing_time': self.processing_time
        }


class TranscriptionBackend(ABC):
    """Abstract base class for transcription backends."""
    
    name: str = "base"
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available and configured."""
        pass
    
    @abstractmethod
    def transcribe(
        self, 
        audio_path: Path,
        language: Optional[str] = None,
        enable_diarization: bool = True
    ) -> TranscriptionResult:
        """
        Transcribe an audio file.
        
        Args:
            audio_path: Path to audio file
            language: Language code (e.g., 'en', 'de') or None for auto-detect
            enable_diarization: Enable speaker diarization
            
        Returns:
            TranscriptionResult with transcript and metadata
        """
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get backend status information."""
        return {
            'name': self.name,
            'available': self.is_available()
        }


class BackendError(Exception):
    """Base exception for backend errors."""
    pass


class BackendUnavailableError(BackendError):
    """Backend is not available or configured."""
    pass


class TranscriptionError(BackendError):
    """Error during transcription."""
    pass
