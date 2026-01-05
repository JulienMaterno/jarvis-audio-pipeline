"""
Move Task: Move processed audio file to "Processed Audiofiles" folder with metadata rename.
Also saves raw transcript to a Transcripts folder.
"""

import logging
from typing import Dict, Any
import os
from pathlib import Path
from datetime import datetime
import json
import re
from src.core.monitor import GoogleDriveMonitor
from src.config import Config

logger = logging.getLogger('Jarvis.Tasks.Move')


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """Sanitize a string for use in filenames."""
    # Remove or replace invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace multiple spaces with single space
    name = re.sub(r'\s+', ' ', name)
    # Truncate if too long
    if len(name) > max_length:
        name = name[:max_length].rsplit(' ', 1)[0]  # Cut at word boundary
    return name.strip()


def generate_new_filename(context: Dict[str, Any]) -> str:
    """Generate a descriptive filename with metadata."""
    # Get analysis results
    analysis = context['task_results'].get('analyze_transcript', {})
    monitor_result = context['task_results'].get('monitor_google_drive', {})
    file_metadata = monitor_result.get('file_metadata', {})
    
    # Get recording date
    original_name = file_metadata.get('name', 'recording')
    modified_time = file_metadata.get('modifiedTime', '')
    
    try:
        if modified_time:
            dt = datetime.fromisoformat(modified_time.replace('Z', '+00:00'))
            date_str = dt.strftime('%Y-%m-%d')
        else:
            date_str = datetime.now().strftime('%Y-%m-%d')
    except (ValueError, AttributeError):
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    # Get category and title
    category = analysis.get('primary_category', 'recording')
    
    # Try to get a meaningful title
    title = None
    if analysis.get('meetings'):
        title = analysis['meetings'][0].get('title', '')
        person = analysis['meetings'][0].get('person_name', '')
        if person and person not in title:
            title = f"{title} with {person}" if title else f"Meeting with {person}"
    elif analysis.get('reflections'):
        title = analysis['reflections'][0].get('title', '')
    
    if not title:
        # Fall back to original filename without extension
        title = Path(original_name).stem
    
    # Sanitize and build filename
    title_clean = sanitize_filename(title)
    
    # Get original extension
    ext = Path(original_name).suffix or '.m4a'
    
    # Format: YYYY-MM-DD_Category_Title.ext
    new_name = f"{date_str}_{category}_{title_clean}{ext}"
    
    return new_name


def move_to_processed(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Move the processed audio file to Processed Audiofiles folder in Google Drive.
    Renames file with metadata: YYYY-MM-DD_Category_Title.ext
    
    Input (from context):
        - file_metadata: File info from monitor task (contains file_id)
        - analyze_transcript: Analysis results for metadata
    
    Output (to context):
        - moved: Boolean indicating if file was moved
        - new_name: New filename with metadata
        - new_location: New folder name
    """
    logger.info("Starting file move task")
    
    monitor_result = context['task_results'].get('monitor_google_drive', {})
    file_metadata = monitor_result.get('file_metadata')
    
    if not file_metadata:
        logger.warning("Missing file metadata, skipping move")
        return {'moved': False}
    
    # Recreate GoogleDriveMonitor (can't pass through XCom)
    gdrive = GoogleDriveMonitor(
        credentials_file=Config.GOOGLE_CREDENTIALS_FILE,
        folder_id=Config.GOOGLE_DRIVE_FOLDER_ID
    )
    
    file_id = file_metadata['id']
    original_name = file_metadata['name']
    processed_folder_id = os.getenv('GOOGLE_DRIVE_PROCESSED_FOLDER_ID')
    
    if not processed_folder_id:
        logger.warning("GOOGLE_DRIVE_PROCESSED_FOLDER_ID not configured, skipping move")
        return {'moved': False}
    
    try:
        # Generate new filename with metadata
        new_name = generate_new_filename(context)
        logger.info(f"Renaming: {original_name} → {new_name}")
        
        # Get the current parent folder
        current_parents = file_metadata.get('parents', [])
        if not current_parents:
            # If no parents in metadata, fetch them
            file_info = gdrive.service.files().get(
                fileId=file_id,
                fields='parents'
            ).execute()
            current_parents = file_info.get('parents', [])
        
        # Build update parameters
        update_params = {
            'fileId': file_id,
            'body': {'name': new_name},
            'fields': 'id, name, parents'
        }
        
        # Only add parent move parameters if we have a current parent
        if current_parents:
            update_params['addParents'] = processed_folder_id
            update_params['removeParents'] = current_parents[0]
        else:
            # If no parents, just rename without moving
            logger.warning("No parent folders found, will rename without moving")
        
        # Move and rename file
        gdrive.service.files().update(**update_params).execute()
        
        if current_parents:
            logger.info(f"Moved and renamed to: {new_name}")
        else:
            logger.info(f"Renamed to: {new_name} (not moved)")
        
        return {
            'moved': bool(current_parents),
            'original_name': original_name,
            'new_name': new_name,
            'new_location': 'Processed Audiofiles' if current_parents else 'Same folder'
        }
        
    except Exception as e:
        logger.error(f"Failed to move file: {e}")
        return {
            'moved': False,
            'error': str(e)
        }
