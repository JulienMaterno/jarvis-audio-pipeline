"""
Test Whisper Transcription
Downloads an audio file from Google Drive and transcribes it locally.
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from gdrive_monitor import GoogleDriveMonitor
from transcriber import WhisperTranscriber
import logging

# Setup simple logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger('WhisperTest')


def test_whisper_transcription():
    """Test downloading and transcribing an audio file."""
    
    print("=" * 70)
    print("Whisper Transcription Test")
    print("=" * 70)
    print()
    
    # Step 1: Connect to Google Drive
    print("📥 Step 1: Connecting to Google Drive...")
    gdrive = GoogleDriveMonitor(
        credentials_file=Config.GOOGLE_CREDENTIALS_FILE,
        folder_id=Config.GOOGLE_DRIVE_FOLDER_ID
    )
    print("   ✓ Connected")
    print()
    
    # Step 2: Get the first audio file
    print("🔍 Step 2: Finding audio files...")
    files = gdrive.list_audio_files(Config.SUPPORTED_FORMATS)
    
    if not files:
        print("   ❌ No audio files found in folder")
        return False
    
    file_to_process = files[0]  # Get the first file
    print(f"   ✓ Found: {file_to_process['name']}")
    print(f"   Size: {int(file_to_process.get('size', 0)) / (1024*1024):.2f} MB")
    print()
    
    # Step 3: Download the file
    print("⬇️  Step 3: Downloading audio file...")
    Config.TEMP_AUDIO_DIR.mkdir(exist_ok=True)
    
    audio_path = gdrive.download_file(
        file_id=file_to_process['id'],
        file_name=file_to_process['name'],
        destination=Config.TEMP_AUDIO_DIR
    )
    
    if not audio_path or not audio_path.exists():
        print("   ❌ Download failed")
        return False
    
    print(f"   ✓ Downloaded to: {audio_path}")
    print()
    
    # Step 4: Transcribe with Whisper
    print("🎤 Step 4: Transcribing with Whisper AI...")
    print("   (This may take a minute - downloading model on first run)")
    print()
    
    transcriber = WhisperTranscriber(model_name='base')  # Using 'base' model
    
    try:
        result = transcriber.transcribe(audio_path)
        
        print("=" * 70)
        print("✓ TRANSCRIPTION COMPLETE")
        print("=" * 70)
        print()
        print(f"📊 Statistics:")
        print(f"   Duration: {result['duration']:.1f} seconds")
        print(f"   Language: {result['language']}")
        print(f"   Text length: {len(result['text'])} characters")
        print()
        print("📝 Transcript:")
        print("-" * 70)
        print(result['text'])
        print("-" * 70)
        print()
        
        # Show formatted version with timestamps
        print("⏱️  Formatted with timestamps:")
        print("-" * 70)
        formatted = transcriber.format_transcript_with_timestamps(result['segments'])
        print(formatted)
        print("-" * 70)
        
        # Clean up
        print()
        print("🧹 Cleaning up temporary file...")
        audio_path.unlink()
        print("   ✓ Deleted temporary file")
        
        print()
        print("=" * 70)
        print("✅ TEST PASSED - Whisper is working perfectly!")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        return False


if __name__ == '__main__':
    try:
        success = test_whisper_transcription()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
