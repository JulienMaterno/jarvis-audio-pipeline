"""
Enhanced Analyze Task: Extract structured multi-database information using Claude AI.
Now delegates to jarvis-intelligence-service.
"""

import logging
import time
import os
import requests
from typing import Dict, Any
from src.supabase.multi_db import SupabaseMultiDatabase

logger = logging.getLogger('Jarvis.Tasks.AnalyzeMulti')

# Retry configuration for API calls
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def analyze_transcript_multi(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Analyze transcript for multi-database routing via Intelligence Service.
    
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
        - transcript_id: ID from Supabase
        - meeting_ids: IDs from Supabase
        - reflection_ids: IDs from Supabase
        - task_ids: IDs from Supabase
    """
    logger.info("Starting multi-database analysis task via Intelligence Service")
    
    # Get results from previous tasks
    transcribe_result = context['task_results'].get('transcribe_audio', {})
    download_result = context['task_results'].get('download_audio_file', {})
    monitor_result = context['task_results'].get('monitor_google_drive', {})
    
    transcript = transcribe_result.get('text')
    file_name = download_result.get('file_name', 'unknown.mp3')
    file_metadata = monitor_result.get('file_metadata', {})
    
    if not transcript:
        raise ValueError("No transcript found in context")
    
    # 1. Save Transcript to Supabase locally
    logger.info("Saving transcript to Supabase...")
    db = SupabaseMultiDatabase()
    transcript_id = db.create_transcript(
        source_file=file_name,
        full_text=transcript,
        audio_duration_seconds=transcribe_result.get('duration'),
        language=transcribe_result.get('language'),
        segments=transcribe_result.get('segments'),
        speakers=transcribe_result.get('speakers'),
        model_used='whisper-large-v3'
    )
    logger.info(f"Transcript saved with ID: {transcript_id}")
    
    # 2. Trigger Intelligence Service
    # INTELLIGENCE_SERVICE_URL should be the base URL (e.g., https://jarvis-intelligence-service-xxx.run.app)
    base_url = os.getenv('INTELLIGENCE_SERVICE_URL', 'http://localhost:8000')
    # Remove trailing slash if present, then append the API path
    base_url = base_url.rstrip('/')
    full_url = f"{base_url}/api/v1/process/{transcript_id}"
    
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Calling Intelligence Service (attempt {attempt + 1}/{MAX_RETRIES})...")
            # We send an empty body or minimal body since ID is in path
            response = requests.post(full_url, json={}, timeout=120) 
            response.raise_for_status()
            
            data = response.json()
            analysis = data.get('analysis', {})
            db_records = data.get('db_records', {})
            
            logger.info(f"✓ Analysis successful: {analysis.get('primary_category', 'unknown')}")
            logger.info(f"✓ DB Records created: {list(db_records.keys())}")
            
            # Merge analysis and db_records for context
            result = analysis.copy()
            result.update(db_records)
            # Ensure transcript_id is in result
            result['transcript_id'] = transcript_id
            
            return result
            
        except Exception as e:
            last_error = e
            logger.warning(f"Analysis attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                sleep_time = RETRY_DELAY * (attempt + 1)
                logger.info(f"Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                logger.error(f"All {MAX_RETRIES} analysis attempts failed")
                raise RuntimeError(f"Intelligence Service failed after {MAX_RETRIES} attempts: {last_error}")
