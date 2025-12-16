"""
Transcription Backends - Flexible GPU/CPU transcription routing.

Supports multiple backends:
- Modal: Cloud GPU via Modal.com (serverless, pay-per-use)
- External: Remote GPU server (laptop/workstation with NVIDIA GPU)
- Local: CPU-based fallback (slow but works anywhere)

Usage:
    from src.core.transcription_backends import get_transcription_router
    
    router = get_transcription_router()
    result = router.transcribe(audio_path)
"""

from .router import TranscriptionRouter, get_transcription_router
from .base import TranscriptionBackend, TranscriptionResult

__all__ = [
    'TranscriptionRouter',
    'get_transcription_router', 
    'TranscriptionBackend',
    'TranscriptionResult'
]
