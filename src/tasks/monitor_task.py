"""
Monitor Task: Check Google Drive for new audio files.
"""

import logging
from typing import Dict, Any, Optional
from src.core.monitor import GoogleDriveMonitor
from src.config import Config

logger = logging.getLogger('Jarvis.Tasks.Monitor')


def monitor_google_drive(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Monitor Google Drive for new unprocessed audio files.
    
    Input (from context):
        - gdrive_monitor: GoogleDriveMonitor instance
        - processed_file_ids: Set of already processed file IDs
        - in_progress_file_ids: Set of file IDs currently being processed
    
    Output (to context):
        - file_metadata: Dict with file info (id, name, size, modifiedTime)
        - file_found: Boolean indicating if new file was found
    """
    logger.info("Starting Google Drive monitoring task")
    
    gdrive = context.get('gdrive_monitor')
    if not gdrive:
        gdrive = GoogleDriveMonitor(
            credentials_file=Config.GOOGLE_CREDENTIALS_FILE,
            folder_id=Config.GOOGLE_DRIVE_FOLDER_ID
        )
    
    processed_ids = context.get('processed_file_ids', set())
    in_progress_ids = context.get('in_progress_file_ids', set())
    
    # Combine processed and in-progress to skip both
    skip_ids = processed_ids | in_progress_ids
    
    # Get latest unprocessed file
    file_metadata = gdrive.get_latest_unprocessed_file(
        supported_formats=Config.SUPPORTED_FORMATS,
        processed_ids=skip_ids
    )
    
    if file_metadata:
        logger.info(f"Found new file: {file_metadata['name']}")
        
        # Mark file as in-progress immediately
        in_progress_ids.add(file_metadata['id'])
        
        return {
            'file_metadata': file_metadata,
            'file_found': True
        }
    else:
        logger.info("No new files to process")
        return {
            'file_metadata': None,
            'file_found': False
        }


def list_all_files(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: List all audio files in Google Drive folder.
    
    Output:
        - all_files: List of all file metadata dicts
        - file_count: Total number of files
    """
    logger.info("Listing all files in Google Drive")
    
    gdrive = context.get('gdrive_monitor')
    if not gdrive:
        gdrive = GoogleDriveMonitor(
            credentials_file=Config.GOOGLE_CREDENTIALS_FILE,
            folder_id=Config.GOOGLE_DRIVE_FOLDER_ID
        )
    
    files = gdrive.list_audio_files(supported_formats=Config.SUPPORTED_FORMATS)
    
    logger.info(f"Found {len(files)} total files")
    return {
        'all_files': files,
        'file_count': len(files)
    }
