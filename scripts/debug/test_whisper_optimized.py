"""
Test optimized faster-whisper transcription on Google Drive audio files.
Uses CTranslate2-optimized Whisper for Intel CPU (3-10× faster).
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
import io

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from transcriber_optimized import OptimizedWhisperTranscriber

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('WhisperTest')

# Load environment
load_dotenv()

def get_google_drive_service():
    """Get authenticated Google Drive service."""
    token_path = project_root / 'token.json'
    
    if not token_path.exists():
        logger.error("No token.json found. Run: python setup_gdrive.py --test")
        sys.exit(1)
    
    creds = Credentials.from_authorized_user_file(str(token_path))
    return build('drive', 'v3', credentials=creds)

def download_file(service, file_id: str, file_name: str, output_dir: Path) -> Path:
    """Download a file from Google Drive."""
    output_path = output_dir / file_name
    
    logger.info(f"Downloading {file_name}...")
    
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            logger.info(f"Download progress: {int(status.progress() * 100)}%")
    
    # Save to file
    with open(output_path, 'wb') as f:
        f.write(fh.getvalue())
    
    logger.info(f"✓ Downloaded to {output_path}")
    return output_path

def main():
    """Test optimized Whisper transcription."""
    
    # Get model from environment
    model_name = os.getenv('WHISPER_MODEL', 'large-v2')
    folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    
    if not folder_id:
        logger.error("GOOGLE_DRIVE_FOLDER_ID not set in .env")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("Testing Optimized Whisper Transcription")
    logger.info("=" * 60)
    logger.info(f"Model: {model_name}")
    logger.info(f"Hardware: Intel Core Ultra 7 258V (CPU optimized)")
    logger.info(f"Backend: faster-whisper (CTranslate2)")
    logger.info("=" * 60)
    
    # Get Google Drive service
    service = get_google_drive_service()
    
    # Get audio files
    query = f"'{folder_id}' in parents and (mimeType contains 'audio/' or name contains '.m4a' or name contains '.mp3')"
    results = service.files().list(
        q=query,
        fields='files(id, name, size, modifiedTime)',
        pageSize=10
    ).execute()
    
    files = results.get('files', [])
    
    if not files:
        logger.error("No audio files found in folder")
        sys.exit(1)
    
    logger.info(f"\nFound {len(files)} audio file(s)")
    
    # Download first file
    file = files[0]
    logger.info(f"\nTesting with: {file['name']}")
    logger.info(f"Size: {int(file['size']) / (1024*1024):.2f} MB")
    
    # Create temp directory
    temp_dir = project_root / 'temp'
    temp_dir.mkdir(exist_ok=True)
    
    # Download file
    audio_path = download_file(service, file['id'], file['name'], temp_dir)
    
    # Initialize transcriber
    logger.info(f"\n{'='*60}")
    logger.info("Initializing Whisper model...")
    logger.info(f"{'='*60}")
    transcriber = OptimizedWhisperTranscriber(model_name=model_name)
    
    # Transcribe
    logger.info(f"\n{'='*60}")
    logger.info("Starting transcription...")
    logger.info(f"{'='*60}")
    
    import time
    start_time = time.time()
    
    result = transcriber.transcribe(audio_path)
    
    elapsed = time.time() - start_time
    audio_duration = result['duration']
    real_time_factor = audio_duration / elapsed if elapsed > 0 else 0
    
    # Display results
    logger.info(f"\n{'='*60}")
    logger.info("TRANSCRIPTION COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Audio duration: {audio_duration:.1f}s")
    logger.info(f"Transcription time: {elapsed:.1f}s")
    logger.info(f"Real-time factor: {real_time_factor:.2f}× (higher is better)")
    logger.info(f"Language: {result['language']} ({result['language_probability']:.1%} confidence)")
    logger.info(f"Segments: {len(result['segments'])}")
    
    logger.info(f"\n{'='*60}")
    logger.info("FULL TRANSCRIPT")
    logger.info(f"{'='*60}")
    print(result['text'])
    
    logger.info(f"\n{'='*60}")
    logger.info("TRANSCRIPT WITH TIMESTAMPS")
    logger.info(f"{'='*60}")
    formatted = transcriber.format_transcript_with_timestamps(result['segments'])
    print(formatted)
    
    # Save transcript
    transcript_path = temp_dir / f"{audio_path.stem}_transcript.txt"
    with open(transcript_path, 'w', encoding='utf-8') as f:
        f.write(f"File: {file['name']}\n")
        f.write(f"Duration: {audio_duration:.1f}s\n")
        f.write(f"Language: {result['language']}\n")
        f.write(f"Transcription time: {elapsed:.1f}s\n")
        f.write(f"Real-time factor: {real_time_factor:.2f}×\n")
        f.write(f"\n{'='*60}\n")
        f.write("FULL TRANSCRIPT\n")
        f.write(f"{'='*60}\n\n")
        f.write(result['text'])
        f.write(f"\n\n{'='*60}\n")
        f.write("TRANSCRIPT WITH TIMESTAMPS\n")
        f.write(f"{'='*60}\n\n")
        f.write(formatted)
    
    logger.info(f"\n✓ Transcript saved to: {transcript_path}")
    
    # Performance summary
    logger.info(f"\n{'='*60}")
    logger.info("PERFORMANCE SUMMARY")
    logger.info(f"{'='*60}")
    if real_time_factor >= 1.0:
        logger.info(f"✓ Transcription is {real_time_factor:.1f}× faster than real-time")
    else:
        logger.info(f"⚠ Transcription is {1/real_time_factor:.1f}× slower than real-time")
    
    logger.info("\n✅ Test complete! Ready to process multiple files.")

if __name__ == '__main__':
    main()
