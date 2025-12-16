"""
Download Task: Download audio file from Google Drive.
"""

import logging
from typing import Dict, Any
from pathlib import Path
from src.core.monitor import GoogleDriveMonitor
from src.config import Config

logger = logging.getLogger('Jarvis.Tasks.Download')


def download_audio_file(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Download audio file from Google Drive to local temp directory.
    
    Input (from context):
        - file_metadata: Dict with file info from monitor task
    
    Output (to context):
        - audio_path: Path to downloaded audio file
        - file_name: Original filename
        - file_id: Google Drive file ID
    """
    logger.info("Starting download task")
    
    monitor_result = context['task_results'].get('monitor_google_drive', {})
    file_metadata = monitor_result.get('file_metadata')
    
    if not file_metadata:
        raise ValueError("No file metadata found in context")
    
    # Recreate GoogleDriveMonitor (can't pass through XCom)
    gdrive = GoogleDriveMonitor(
        credentials_file=Config.GOOGLE_CREDENTIALS_FILE,
        folder_id=Config.GOOGLE_DRIVE_FOLDER_ID
    )
    
    file_id = file_metadata['id']
    file_name = file_metadata['name']
    
    # Ensure temp directory exists
    Config.TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Downloading: {file_name}")
    
    # Download file
    audio_path = gdrive.download_file(
        file_id=file_id,
        file_name=file_name,
        destination=Config.TEMP_AUDIO_DIR
    )
    
    if not audio_path or not audio_path.exists():
        raise Exception(f"Failed to download file: {file_name}")
    
    logger.info(f"Downloaded to: {audio_path}")
    
    return {
        'audio_path': str(audio_path),  # Convert Path to string for XCom
        'file_name': file_name,
        'file_id': file_id
    }
