"""
Cleanup Task: Clean up temporary files after processing.
"""

import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger('Jarvis.Tasks.Cleanup')


def cleanup_temp_files(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Delete temporary audio file after successful processing.
    
    Input (from context):
        - audio_path: Path to temporary audio file (from download task)
    
    Output (to context):
        - cleanup_success: Boolean indicating if cleanup succeeded
        - deleted_file: Path that was deleted
    """
    logger.info("Starting cleanup task")
    
    download_result = context['task_results'].get('download_audio_file', {})
    audio_path = download_result.get('audio_path')
    
    if not audio_path:
        logger.warning("No audio path found, skipping cleanup")
        return {
            'cleanup_success': False,
            'deleted_file': None
        }
    
    if not isinstance(audio_path, Path):
        audio_path = Path(audio_path)
    
    if not audio_path.exists():
        logger.warning(f"File already deleted or not found: {audio_path}")
        return {
            'cleanup_success': True,
            'deleted_file': str(audio_path)
        }
    
    try:
        audio_path.unlink()
        logger.info(f"Deleted temporary file: {audio_path.name}")
        return {
            'cleanup_success': True,
            'deleted_file': str(audio_path)
        }
    except Exception as e:
        logger.error(f"Failed to delete temporary file: {e}")
        return {
            'cleanup_success': False,
            'deleted_file': str(audio_path),
            'error': str(e)
        }


def cleanup_old_logs(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Clean up old log files (optional maintenance task).
    
    Input (from context):
        - max_log_age_days: Maximum age of logs to keep (default: 30)
    
    Output (to context):
        - logs_deleted: Number of log files deleted
        - space_freed_mb: Approximate space freed in MB
    """
    from datetime import datetime, timedelta
    from src.config import Config
    
    logger.info("Starting log cleanup task")
    
    max_age_days = context.get('max_log_age_days', 30)
    cutoff_date = datetime.now() - timedelta(days=max_age_days)
    
    log_dir = Config.LOG_DIR
    if not log_dir.exists():
        return {
            'logs_deleted': 0,
            'space_freed_mb': 0
        }
    
    deleted_count = 0
    space_freed = 0
    
    for log_file in log_dir.glob('*.log'):
        try:
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff_date:
                size = log_file.stat().st_size
                log_file.unlink()
                deleted_count += 1
                space_freed += size
                logger.debug(f"Deleted old log: {log_file.name}")
        except Exception as e:
            logger.warning(f"Failed to delete log {log_file.name}: {e}")
    
    space_freed_mb = space_freed / (1024 * 1024)
    logger.info(f"Cleaned up {deleted_count} old logs, freed {space_freed_mb:.2f} MB")
    
    return {
        'logs_deleted': deleted_count,
        'space_freed_mb': space_freed_mb
    }
