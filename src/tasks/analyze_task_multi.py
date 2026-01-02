"""
Enhanced Analyze Task: Extract structured multi-database information using Claude AI.
Now delegates to jarvis-intelligence-service.
"""

import logging
import time
import os
import requests
from typing import Dict, Any, Optional
from src.supabase.multi_db import SupabaseMultiDatabase

logger = logging.getLogger('Jarvis.Tasks.AnalyzeMulti')

# Retry configuration for API calls
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def get_identity_token(audience: str) -> Optional[str]:
    """
    Get Google Cloud identity token for service-to-service authentication.
    
    In Cloud Run, this uses the metadata server to get a token.
    Locally, it tries to use the default credentials.
    
    Args:
        audience: The URL of the service to authenticate to (e.g., the Intelligence Service URL)
    
    Returns:
        Identity token string, or None if running locally without auth
    """
    try:
        # Try Cloud Run metadata server first (fastest, works in Cloud Run)
        metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
        response = requests.get(
            metadata_url,
            params={"audience": audience},
            headers={"Metadata-Flavor": "Google"},
            timeout=2
        )
        if response.status_code == 200:
            logger.debug("Got identity token from metadata server")
            return response.text
    except requests.exceptions.RequestException:
        logger.debug("Metadata server not available (not running in Cloud Run)")
    
    # Try google-auth library as fallback (for local development with ADC)
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token
        
        auth_request = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_request, audience)
        logger.debug("Got identity token from google-auth library")
        return token
    except Exception as e:
        logger.debug(f"Could not get identity token from google-auth: {e}")
    
    logger.warning("Could not obtain identity token - requests may fail with 403")
    return None


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
    
    # Get identity token for Cloud Run authentication
    # The audience should be the base URL of the Intelligence Service
    identity_token = get_identity_token(base_url)
    headers = {}
    if identity_token:
        headers["Authorization"] = f"Bearer {identity_token}"
        logger.info("Using identity token for authentication")
    else:
        logger.warning("No identity token available - may fail if auth required")
    
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Calling Intelligence Service (attempt {attempt + 1}/{MAX_RETRIES})...")
            # We send an empty body or minimal body since ID is in path
            response = requests.post(full_url, json={}, headers=headers, timeout=120) 
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
