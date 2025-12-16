"""
Enhanced Analyze Task: Extract structured multi-database information using Claude AI.
"""

import logging
import time
from typing import Dict, Any
import os
from src.analyzers.multi_db_analyzer import ClaudeMultiAnalyzer

logger = logging.getLogger('Jarvis.Tasks.AnalyzeMulti')

# Retry configuration for API calls
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Global analyzer instance
_analyzer = None


def get_analyzer() -> ClaudeMultiAnalyzer:
    """Get or create global multi-analyzer instance."""
    global _analyzer
    if _analyzer is None:
        api_key = os.getenv('CLAUDE_API_KEY')
        if not api_key:
            raise ValueError("CLAUDE_API_KEY not found in environment")
        _analyzer = ClaudeMultiAnalyzer(api_key=api_key)
    return _analyzer


def analyze_transcript_multi(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Analyze transcript for multi-database routing.
    
    Input (from context):
        - transcript: Full transcript text (from transcribe task)
        - file_name: Original filename (from download task)
        - file_metadata: File metadata with modifiedTime (from monitor task)
    
    Output (to context):
        - primary_category: 'meeting', 'reflection', 'task_planning', or 'other'
        - meeting: Meeting data dict or None
        - reflection: Reflection data dict or None
        - tasks: List of task dicts
        - crm_updates: List of CRM update dicts
        - (All fields from Claude's structured output)
    """
    logger.info("Starting multi-database analysis task")
    
    # Get results from previous tasks
    transcribe_result = context['task_results'].get('transcribe_audio', {})
    download_result = context['task_results'].get('download_audio_file', {})
    monitor_result = context['task_results'].get('monitor_google_drive', {})
    
    transcript = transcribe_result.get('text')
    file_name = download_result.get('file_name', 'unknown.mp3')
    file_metadata = monitor_result.get('file_metadata', {})
    
    if not transcript:
        raise ValueError("No transcript found in context")
    
    # Get recording date from file metadata
    recording_date = None
    if file_metadata and 'modifiedTime' in file_metadata:
        try:
            from datetime import datetime
            modified_time = file_metadata['modifiedTime']
            # Parse ISO format: 2025-11-22T04:55:03.463803Z
            dt = datetime.fromisoformat(modified_time.replace('Z', '+00:00'))
            recording_date = dt.date().isoformat()
        except Exception as e:
            logger.warning(f"Could not parse file date: {e}")
    
    logger.info(f"Analyzing transcript from: {file_name}")
    logger.info(f"Transcript length: {len(transcript)} characters")
    logger.info(f"Recording date: {recording_date or 'using today'}")
    
    # Analyze with retry logic
    analyzer = get_analyzer()
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Analyzing transcript (attempt {attempt + 1}/{MAX_RETRIES})...")
            result = analyzer.analyze_transcript(transcript, file_name, recording_date)
            logger.info(f"✓ Analysis successful: {result.get('primary_category', 'unknown')}")
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"Analysis attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                sleep_time = RETRY_DELAY * (attempt + 1)  # Exponential backoff
                logger.info(f"Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                logger.error(f"All {MAX_RETRIES} analysis attempts failed")
                raise RuntimeError(f"Claude API analysis failed after {MAX_RETRIES} attempts: {last_error}")
