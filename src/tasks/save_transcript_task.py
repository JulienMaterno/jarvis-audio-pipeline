"""
Save Transcript Task: Save raw transcript to a Transcripts folder with metadata.
"""

import logging
from typing import Dict, Any
import os
from pathlib import Path
from datetime import datetime
import json
import re

logger = logging.getLogger('Jarvis.Tasks.SaveTranscript')

# Default transcripts folder (can be overridden by env var)
DEFAULT_TRANSCRIPTS_FOLDER = Path(__file__).parent.parent.parent.parent / 'Transcripts'


def get_transcripts_folder() -> Path:
    """Get the transcripts folder path."""
    folder = os.getenv('TRANSCRIPTS_FOLDER', str(DEFAULT_TRANSCRIPTS_FOLDER))
    return Path(folder)


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """Sanitize a string for use in filenames."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name)
    if len(name) > max_length:
        name = name[:max_length].rsplit(' ', 1)[0]
    return name.strip()


def save_transcript(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Save the raw transcript to a Transcripts folder with matching filename.
    
    Saves two files:
    1. {name}.txt - Raw transcript text
    2. {name}.json - Full transcript data with metadata
    
    Input (from context):
        - transcribe_audio: Transcription results
        - analyze_transcript: Analysis results (for naming)
        - file_metadata: Original file info
    
    Output (to context):
        - transcript_saved: Boolean
        - transcript_path: Path to saved transcript
        - metadata_path: Path to saved metadata JSON
    """
    logger.info("Starting transcript save task")
    
    # Get results from previous tasks
    transcribe_result = context['task_results'].get('transcribe_audio', {})
    analysis = context['task_results'].get('analyze_transcript', {})
    monitor_result = context['task_results'].get('monitor_google_drive', {})
    move_result = context['task_results'].get('move_to_processed', {})
    file_metadata = monitor_result.get('file_metadata', {})
    
    transcript_text = transcribe_result.get('text', '')
    if not transcript_text:
        logger.warning("No transcript text found, skipping save")
        return {'transcript_saved': False}
    
    # Get the transcripts folder
    transcripts_folder = get_transcripts_folder()
    transcripts_folder.mkdir(parents=True, exist_ok=True)
    
    # Use the same name as the processed audio file (from move task)
    # or generate one if move task hasn't run
    if move_result.get('new_name'):
        base_name = Path(move_result['new_name']).stem
    else:
        # Generate filename from metadata
        original_name = file_metadata.get('name', 'transcript')
        modified_time = file_metadata.get('modifiedTime', '')
        
        try:
            if modified_time:
                dt = datetime.fromisoformat(modified_time.replace('Z', '+00:00'))
                date_str = dt.strftime('%Y-%m-%d')
            else:
                date_str = datetime.now().strftime('%Y-%m-%d')
        except:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        category = analysis.get('primary_category', 'recording')
        
        # Get title
        title = None
        if analysis.get('meetings'):
            title = analysis['meetings'][0].get('title', '')
        elif analysis.get('reflections'):
            title = analysis['reflections'][0].get('title', '')
        
        if not title:
            title = Path(original_name).stem
        
        title_clean = sanitize_filename(title)
        base_name = f"{date_str}_{category}_{title_clean}"
    
    # Save raw transcript as .txt
    txt_path = transcripts_folder / f"{base_name}.txt"
    txt_path.write_text(transcript_text, encoding='utf-8')
    logger.info(f"Saved transcript: {txt_path.name}")
    
    # Build comprehensive metadata
    metadata = {
        'filename': base_name,
        'original_audio_file': file_metadata.get('name', 'unknown'),
        'processed_audio_file': move_result.get('new_name', file_metadata.get('name', 'unknown')),
        'created_at': datetime.now().isoformat(),
        'recording_date': file_metadata.get('modifiedTime', ''),
        
        # Transcription info
        'transcription': {
            'backend': transcribe_result.get('backend', 'unknown'),
            'model': transcribe_result.get('model', 'unknown'),
            'duration_seconds': transcribe_result.get('duration', 0),
            'language': transcribe_result.get('language', 'unknown'),
            'speakers': transcribe_result.get('speakers', []),
            'processing_time_seconds': transcribe_result.get('processing_time', 0),
        },
        
        # Full transcript with segments
        'transcript': {
            'text': transcript_text,
            'segments': transcribe_result.get('segments', []),
        },
        
        # Analysis summary
        'analysis': {
            'primary_category': analysis.get('primary_category', 'unknown'),
            'meetings_count': len(analysis.get('meetings', [])),
            'reflections_count': len(analysis.get('reflections', [])),
            'tasks_count': len(analysis.get('tasks', [])),
            'crm_updates_count': len(analysis.get('crm_updates', [])),
        },
        
        # Full analysis data
        'analysis_full': analysis,
    }
    
    # Save metadata as .json
    json_path = transcripts_folder / f"{base_name}.json"
    json_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')
    logger.info(f"Saved metadata: {json_path.name}")
    
    return {
        'transcript_saved': True,
        'transcript_path': str(txt_path),
        'metadata_path': str(json_path),
        'base_name': base_name,
    }
