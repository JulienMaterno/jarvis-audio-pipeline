"""
Transcription Router - Intelligent backend selection and failover.

Automatically routes transcription requests to the best available backend:
1. External GPU (if configured and reachable) - Free, uses your hardware
2. Modal (if configured) - Serverless GPU, pay-per-use
3. Local (fallback) - CPU-based, slow but always works

Configuration:
    TRANSCRIPTION_BACKEND: Force a specific backend (external_gpu, modal, local)
    EXTERNAL_GPU_URL: URL of external GPU server
    MODAL_ENABLED: Enable Modal backend (true/false)
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

from .base import (
    TranscriptionBackend,
    TranscriptionResult,
    BackendUnavailableError,
    TranscriptionError
)

logger = logging.getLogger('Jarvis.Transcription.Router')

# Global router instance
_router = None


class TranscriptionRouter:
    """
    Routes transcription to the best available backend.
    
    Priority order (configurable):
    1. External GPU - Your laptop/workstation with NVIDIA GPU
    2. Modal - Serverless cloud GPU
    3. Local - CPU fallback
    
    Supports automatic failover if a backend fails.
    """
    
    def __init__(
        self,
        model_name: str = "large-v3",
        enable_diarization: bool = True,
        preferred_backend: Optional[str] = None,
        enable_failover: bool = True,
    ):
        """
        Initialize transcription router.
        
        Args:
            model_name: Whisper model to use
            enable_diarization: Enable speaker diarization
            preferred_backend: Force specific backend (external_gpu, modal, local)
            enable_failover: Try other backends if preferred fails
        """
        self.model_name = model_name
        self.enable_diarization = enable_diarization
        self.enable_failover = enable_failover
        
        # Override from environment
        self.preferred_backend = preferred_backend or os.getenv('TRANSCRIPTION_BACKEND')
        
        # Initialize backends lazily
        self._backends: dict = {}
        self._backend_order = ['external_gpu', 'modal', 'local']
        
    def _get_backend(self, name: str) -> TranscriptionBackend:
        """Get or create a backend by name."""
        if name not in self._backends:
            if name == 'external_gpu':
                from .external_backend import ExternalGPUBackend
                self._backends[name] = ExternalGPUBackend()
            elif name == 'modal':
                from .modal_backend import ModalBackend
                # Check if Modal is enabled
                modal_enabled = os.getenv('MODAL_ENABLED', 'true').lower() == 'true'
                if modal_enabled:
                    self._backends[name] = ModalBackend(
                        model_name=self.model_name,
                        gpu_type=os.getenv('MODAL_GPU_TYPE', 'T4')
                    )
                else:
                    return None
            elif name == 'local':
                from .local_backend import LocalBackend
                self._backends[name] = LocalBackend(
                    model_name=self.model_name,
                    enable_diarization=self.enable_diarization
                )
            else:
                raise ValueError(f"Unknown backend: {name}")
        
        return self._backends.get(name)
    
    def get_available_backends(self) -> List[str]:
        """Get list of available backends."""
        available = []
        for name in self._backend_order:
            backend = self._get_backend(name)
            if backend and backend.is_available():
                available.append(name)
        return available
    
    def get_best_backend(self) -> Optional[TranscriptionBackend]:
        """Get the best available backend based on priority."""
        # If preferred backend is set, try it first
        if self.preferred_backend:
            backend = self._get_backend(self.preferred_backend)
            if backend and backend.is_available():
                return backend
            logger.warning(f"Preferred backend '{self.preferred_backend}' not available")
        
        # Otherwise, find first available by priority
        for name in self._backend_order:
            backend = self._get_backend(name)
            if backend and backend.is_available():
                return backend
        
        return None
    
    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        enable_diarization: Optional[bool] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio using the best available backend.
        
        Args:
            audio_path: Path to audio file
            language: Language code or None for auto-detect
            enable_diarization: Override default diarization setting
            
        Returns:
            TranscriptionResult with transcript and metadata
        """
        if enable_diarization is None:
            enable_diarization = self.enable_diarization
        
        # Get backends to try
        backends_to_try = []
        
        if self.preferred_backend:
            backend = self._get_backend(self.preferred_backend)
            if backend:
                backends_to_try.append((self.preferred_backend, backend))
        
        if self.enable_failover or not backends_to_try:
            for name in self._backend_order:
                if name != self.preferred_backend:
                    backend = self._get_backend(name)
                    if backend:
                        backends_to_try.append((name, backend))
        
        # Try each backend
        last_error = None
        for name, backend in backends_to_try:
            if not backend.is_available():
                logger.debug(f"Backend '{name}' not available, skipping")
                continue
            
            try:
                logger.info(f"Using backend: {name}")
                result = backend.transcribe(
                    audio_path,
                    language=language,
                    enable_diarization=enable_diarization
                )
                return result
                
            except Exception as e:
                logger.warning(f"Backend '{name}' failed: {e}")
                last_error = e
                
                if not self.enable_failover:
                    raise
        
        # All backends failed
        if last_error:
            raise TranscriptionError(f"All backends failed. Last error: {last_error}")
        else:
            raise BackendUnavailableError("No transcription backends available")
    
    def get_status(self) -> dict:
        """Get status of all backends."""
        status = {
            'preferred_backend': self.preferred_backend,
            'failover_enabled': self.enable_failover,
            'backends': {}
        }
        
        for name in self._backend_order:
            backend = self._get_backend(name)
            if backend:
                status['backends'][name] = backend.get_status()
            else:
                status['backends'][name] = {'available': False, 'reason': 'disabled'}
        
        return status


def get_transcription_router(
    model_name: Optional[str] = None,
    enable_diarization: Optional[bool] = None,
) -> TranscriptionRouter:
    """
    Get or create the global transcription router.
    
    Configuration via environment:
        WHISPER_MODEL: Model name (default: large-v3)
        ENABLE_DIARIZATION: Enable diarization (default: true)
        TRANSCRIPTION_BACKEND: Force backend (external_gpu, modal, local)
        EXTERNAL_GPU_URL: URL of external GPU server
        MODAL_ENABLED: Enable Modal (default: true)
    """
    global _router
    
    if _router is None:
        _router = TranscriptionRouter(
            model_name=model_name or os.getenv('WHISPER_MODEL', 'large-v3'),
            enable_diarization=enable_diarization if enable_diarization is not None 
                else os.getenv('ENABLE_DIARIZATION', 'true').lower() == 'true',
        )
    
    return _router


def reset_router():
    """Reset the global router (for testing)."""
    global _router
    _router = None
