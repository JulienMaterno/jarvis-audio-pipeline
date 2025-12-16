"""Quick test of Modal WhisperX transcription using the new class-based v2 app."""
import modal
import sys
import time
from pathlib import Path


def test_with_modal_cls(audio_path: str):
    """Test transcription using modal.Cls (v2 app)."""
    print(f"\nTesting with Modal Cls (v2): {audio_path}")
    
    # Read audio file
    path = Path(audio_path)
    audio_bytes = path.read_bytes()
    print(f"Sending {len(audio_bytes)/1024/1024:.1f}MB to Modal...")
    
    start = time.time()
    
    # Get deployed class
    WhisperTranscriber = modal.Cls.from_name("jarvis-whisperx", "WhisperTranscriber")
    transcriber = WhisperTranscriber()
    
    # Call remote transcribe method
    result = transcriber.transcribe.remote(
        audio_bytes=audio_bytes,
        filename=path.name,
        enable_diarization=True
    )
    
    total_time = time.time() - start
    duration = result.get('duration', 0)
    speed = duration / total_time if total_time > 0 else 0
    
    print(f"\n✅ Transcription complete!")
    print(f"Duration: {duration:.1f}s audio")
    print(f"Processing time: {total_time:.1f}s ({speed:.1f}x realtime)")
    print(f"Language: {result['language']}")
    print(f"Speakers: {result.get('speakers', [])}")
    print(f"\n--- Transcript (first 500 chars) ---")
    text = result.get('text', '')
    print(text[:500] + "..." if len(text) > 500 else text)
    
    return result


def test_with_backend(audio_path: str):
    """Test transcription using the TranscriptionRouter (full pipeline)."""
    print(f"\nTesting with TranscriptionRouter: {audio_path}")
    
    from src.core.transcription_backends import get_transcription_router
    
    path = Path(audio_path)
    router = get_transcription_router()
    
    print(f"Available backends: {router.get_available_backends()}")
    
    start = time.time()
    result = router.transcribe(path)
    total_time = time.time() - start
    
    speed = result.duration / total_time if total_time > 0 else 0
    
    print(f"\n✅ Transcription complete!")
    print(f"Backend used: {result.backend}")
    print(f"Duration: {result.duration:.1f}s audio")
    print(f"Processing time: {total_time:.1f}s ({speed:.1f}x realtime)")
    print(f"Language: {result.language}")
    print(f"Speakers: {result.speakers}")
    print(f"\n--- Transcript (first 500 chars) ---")
    print(result.text[:500] + "..." if len(result.text) > 500 else result.text)
    
    return result


if __name__ == "__main__":
    import os
    
    # Default test file
    default_path = r"C:\Users\aaron\My Drive\Jarvis\Audiofiles\27. Nov 2025 at 20 40.m4a"
    
    audio_path = sys.argv[1] if len(sys.argv) > 1 else default_path
    
    if not os.path.exists(audio_path):
        print(f"Audio file not found: {audio_path}")
        print("Usage: python test_modal.py <audio_file>")
        sys.exit(1)
    
    # Test with direct Modal call
    test_with_modal_cls(audio_path)
    
    # Test with TranscriptionRouter
    print("\n" + "="*60)
    test_with_backend(audio_path)
