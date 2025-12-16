"""
Transcribe Task: Transcribe audio using GPU backends (Modal/External) with local fallback.

Supports multiple backends:
- External GPU: Your laptop/workstation with NVIDIA GPU (free, fastest)
- Modal: Serverless cloud GPU (pay-per-use, ~$0.10-0.30/hour)
- Local: CPU fallback (slow but always works)

Configure via environment:
    TRANSCRIPTION_BACKEND: Force backend (external_gpu, modal, local)
    EXTERNAL_GPU_URL: URL of external GPU server (e.g., http://laptop:8000)
    MODAL_ENABLED: Enable Modal backend (true/false)
"""

import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger('Jarvis.Tasks.Transcribe')

# Global router instance
_router = None


def get_transcription_router():
    """Get or create global transcription router."""
    global _router
    if _router is None:
        from src.core.transcription_backends import get_transcription_router
        _router = get_transcription_router()
    return _router


def transcribe_audio(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Transcribe audio file using best available GPU backend.
    
    Backend priority:
    1. External GPU (if EXTERNAL_GPU_URL set and reachable)
    2. Modal (if authenticated)
    3. Local CPU (fallback)
    
    Input (from context):
        - audio_path: Path to audio file (from download task)
    
    Output (to context):
        - transcript: Full transcript text
        - transcript_data: Complete transcript data dict
        - duration: Audio duration in seconds
        - language: Detected language
        - backend: Which backend was used (external_gpu, modal, local)
    """
    logger.info("Starting transcription task")
    
    download_result = context['task_results'].get('download_audio_file', {})
    audio_path = download_result.get('audio_path')
    
    if not audio_path:
        raise ValueError("No audio path found in context")
    
    if not isinstance(audio_path, Path):
        audio_path = Path(audio_path)
    
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    # Check audio duration
    try:
        from pydub.utils import mediainfo
        info = mediainfo(str(audio_path))
        duration_sec = float(info.get('duration', 0))
        duration_min = duration_sec / 60
        logger.info(f"Audio duration: {duration_min:.1f} minutes")
    except Exception as e:
        logger.debug(f"Could not get audio duration: {e}")
    
    logger.info(f"Transcribing: {audio_path.name}")
    
    # Get router and transcribe (auto-selects best backend)
    router = get_transcription_router()
    
    # Log available backends
    available = router.get_available_backends()
    logger.info(f"Available backends: {', '.join(available) if available else 'none'}")
    
    # Transcribe using best available backend
    result = router.transcribe(audio_path)
    transcript_data = result.to_dict()
    
    transcript_text = transcript_data['text']
    duration = transcript_data['duration']
    language = transcript_data['language']
    speakers = transcript_data.get('speakers', [])
    backend = transcript_data.get('backend', 'unknown')
    processing_time = transcript_data.get('processing_time', 0)
    
    logger.info(f"Transcription complete via {backend}: {len(transcript_text)} chars, {duration:.1f}s audio in {processing_time:.1f}s")
    if speakers:
        logger.info(f"Speakers identified: {', '.join(speakers)}")
    
    return {
        'text': transcript_text,
        'transcript': transcript_text,  # Backward compatibility
        'transcript_data': transcript_data,
        'duration': duration,
        'language': language,
        'segments': transcript_data.get('segments', []),
        'speakers': speakers,
        'backend': backend,  # New: which backend was used
        'processing_time': processing_time,
    }


def format_transcript_with_timestamps(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Format transcript with timestamps for better readability.
    
    Input (from context):
        - transcript_data: Complete transcript data from transcribe task
    
    Output (to context):
        - formatted_transcript: Transcript with timestamps
    """
    logger.info("Formatting transcript with timestamps")
    
    transcribe_result = context['task_results'].get('transcribe_audio', {})
    transcript_data = transcribe_result.get('transcript_data')
    
    if not transcript_data:
        raise ValueError("No transcript data found in context")
    
    # Format segments with timestamps and speakers
    segments = transcript_data.get('segments', [])
    formatted_lines = []
    current_speaker = None
    
    for segment in segments:
        speaker = segment.get('speaker', 'Unknown')
        text = segment['text'].strip()
        start = _format_timestamp(segment['start'])
        end = _format_timestamp(segment['end'])
        
        if speaker != current_speaker:
            formatted_lines.append(f"\n[{speaker}]")
            current_speaker = speaker
        
        formatted_lines.append(f"  [{start} - {end}] {text}")
    
    return {
        'formatted_transcript': '\n'.join(formatted_lines)
    }


def _format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"