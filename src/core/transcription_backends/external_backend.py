"""
External GPU Backend - HTTP API for remote GPU server.

Connect to a laptop/workstation with NVIDIA GPU running WhisperX.
This is perfect for using an existing GPU machine without cloud costs.

Server Setup (on GPU laptop):
    pip install whisperx fastapi uvicorn python-multipart
    python -m src.core.transcription_backends.external_server --port 8000
    
Client Usage:
    Set EXTERNAL_GPU_URL=http://laptop-ip:8000
    
    from src.core.transcription_backends import get_transcription_router
    router = get_transcription_router()
    result = router.transcribe(audio_path)  # Auto-routes to external GPU
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests

from .base import (
    TranscriptionBackend,
    TranscriptionResult,
    BackendUnavailableError,
    TranscriptionError
)

logger = logging.getLogger('Jarvis.Transcription.External')


class ExternalGPUBackend(TranscriptionBackend):
    """
    Transcription backend using external GPU server via HTTP API.
    
    Connect to any machine running the WhisperX server:
    - Laptop with NVIDIA GPU
    - Workstation
    - Self-hosted GPU server
    
    Zero cloud costs - use hardware you already have!
    """
    
    name = "external_gpu"
    
    def __init__(
        self,
        server_url: Optional[str] = None,
        timeout: int = 3600,  # 1 hour
        api_key: Optional[str] = None,
    ):
        """
        Initialize external GPU backend.
        
        Args:
            server_url: URL of GPU server (default: from EXTERNAL_GPU_URL env)
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
        """
        self.server_url = server_url or os.getenv('EXTERNAL_GPU_URL')
        self.timeout = timeout
        self.api_key = api_key or os.getenv('EXTERNAL_GPU_API_KEY')
        
    def is_available(self) -> bool:
        """Check if external GPU server is reachable."""
        if not self.server_url:
            logger.debug("EXTERNAL_GPU_URL not set")
            return False
        
        try:
            response = requests.get(
                f"{self.server_url}/health",
                timeout=5,
                headers=self._get_headers()
            )
            return response.status_code == 200
        except requests.RequestException as e:
            logger.debug(f"External GPU server not reachable: {e}")
            return False
    
    def _get_headers(self) -> dict:
        """Get request headers including auth if configured."""
        headers = {}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers
    
    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        enable_diarization: bool = True
    ) -> TranscriptionResult:
        """Transcribe audio using external GPU server."""
        if not self.server_url:
            raise BackendUnavailableError("EXTERNAL_GPU_URL not configured")
        
        start_time = time.time()
        logger.info(f"Sending {audio_path.name} to external GPU server...")
        
        try:
            # Prepare multipart form data
            with open(audio_path, 'rb') as f:
                files = {'file': (audio_path.name, f, 'audio/mpeg')}
                data = {
                    'language': language or '',
                    'enable_diarization': str(enable_diarization).lower(),
                }
                
                response = requests.post(
                    f"{self.server_url}/transcribe",
                    files=files,
                    data=data,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
            
            if response.status_code != 200:
                error_detail = response.json().get('detail', response.text)
                raise TranscriptionError(f"Server error: {error_detail}")
            
            result = response.json()
            processing_time = time.time() - start_time
            
            logger.info(f"External GPU transcription complete in {processing_time:.1f}s")
            
            return TranscriptionResult(
                text=result['text'],
                segments=result['segments'],
                language=result['language'],
                duration=result['duration'],
                speakers=result.get('speakers', []),
                backend="external_gpu",
                model=result.get('model', 'unknown'),
                processing_time=processing_time,
            )
            
        except requests.RequestException as e:
            logger.error(f"External GPU request failed: {e}")
            raise TranscriptionError(f"External GPU request failed: {e}") from e
        except Exception as e:
            logger.error(f"External GPU transcription failed: {e}")
            raise TranscriptionError(f"External GPU transcription failed: {e}") from e
    
    def get_status(self) -> dict:
        """Get external GPU backend status."""
        status = {
            'name': self.name,
            'available': self.is_available(),
            'server_url': self.server_url,
        }
        
        # Try to get server info
        if self.is_available():
            try:
                response = requests.get(
                    f"{self.server_url}/info",
                    timeout=5,
                    headers=self._get_headers()
                )
                if response.status_code == 200:
                    status.update(response.json())
            except Exception:
                pass
        
        return status
