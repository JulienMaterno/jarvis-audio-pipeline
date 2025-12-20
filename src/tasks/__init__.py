"""Task module init - exports all task functions."""

from .monitor_task import monitor_google_drive
from .download_task import download_audio_file
from .transcribe_task import transcribe_audio
from .analyze_task_multi import analyze_transcript_multi  # Main path: calls Intelligence Service
from .move_task import move_to_processed
from .save_transcript_task import save_transcript
from .cleanup_task import cleanup_temp_files

# DEPRECATED: These are no longer used in the main pipeline
# All analysis now goes through Intelligence Service via analyze_transcript_multi
from .supabase_task import save_to_supabase  # DEPRECATED
from .notion_task import save_to_notion  # DEPRECATED
from .notion_task_multi import save_to_notion_multi  # DEPRECATED

__all__ = [
    # Core pipeline tasks
    'monitor_google_drive',
    'download_audio_file',
    'transcribe_audio',
    'analyze_transcript_multi',  # Uses Intelligence Service
    'save_to_supabase',
    'move_to_processed',
    'save_transcript',
    'cleanup_temp_files',
    # Legacy (for backwards compatibility)
    'save_to_notion',
    'save_to_notion_multi',
]
