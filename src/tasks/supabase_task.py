"""
Supabase Save Task: Save to Meetings, Reflections, Tasks, and update CRM.
Replaces notion_task_multi.py - writes to Supabase instead of Notion.
"""

import logging
from typing import Dict, Any
from src.supabase.multi_db import SupabaseMultiDatabase

logger = logging.getLogger('Jarvis.Tasks.SupabaseSave')

# Global Supabase client
_supabase_multi = None


def get_supabase_multi() -> SupabaseMultiDatabase:
    """Get or create global Supabase multi-database client."""
    global _supabase_multi
    if _supabase_multi is None:
        _supabase_multi = SupabaseMultiDatabase()
    return _supabase_multi


def save_to_supabase(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Save analyzed content to Supabase tables.
    
    Input (from context):
        - primary_category: Main category (from analyze_multi task)
        - meetings: List of meeting data (from analyze_multi task)
        - reflections: List of reflection data (from analyze_multi task)
        - tasks: List of tasks (from analyze_multi task)
        - crm_updates: List of CRM updates (from analyze_multi task)
        - transcript: Full transcript (from transcribe task)
        - duration: Audio duration (from transcribe task)
        - file_name: Original filename (from download task)
        - run_id: Pipeline run ID for logging
    
    Output (to context):
        - transcript_id: Created transcript ID
        - meeting_ids: List of created meeting IDs
        - reflection_ids: List of created reflection IDs
        - task_ids: List of created task IDs
        - crm_updated_ids: List of updated CRM contact IDs
        - save_success: Boolean
    """
    logger.info("Starting Supabase save task")
    
    # Get results from previous tasks
    analyze_result = context['task_results'].get('analyze_transcript_multi', {})
    transcribe_result = context['task_results'].get('transcribe_audio', {})
    download_result = context['task_results'].get('download_audio_file', {})
    
    primary_category = analyze_result.get('primary_category', 'other')
    meetings_data = analyze_result.get('meetings', [])
    reflections_data = analyze_result.get('reflections', [])
    tasks_data = analyze_result.get('tasks', [])
    crm_updates = analyze_result.get('crm_updates', [])
    
    transcript = transcribe_result.get('text', '')
    duration = transcribe_result.get('duration', 0)
    language = transcribe_result.get('language', 'en')
    segments = transcribe_result.get('segments', [])
    speakers = transcribe_result.get('speakers', [])
    
    file_name = download_result.get('file_name', 'unknown.m4a')
    run_id = context.get('run_id')
    
    # Get Supabase client
    db = get_supabase_multi()
    
    result = {
        'transcript_id': None,
        'meeting_ids': [],
        'meeting_urls': [],
        'reflection_ids': [],
        'reflection_urls': [],
        'task_ids': [],
        'task_urls': [],
        'crm_updated_ids': [],
        'save_success': False,
        'primary_type': None,
        'primary_id': None,
    }
    
    try:
        # Step 1: Create transcript record
        logger.info("Creating transcript record...")
        transcript_id = db.create_transcript(
            source_file=file_name,
            full_text=transcript,
            audio_duration_seconds=duration,
            language=language,
            segments=segments,
            speakers=speakers,
            model_used='whisper-large-v3'  # Could be dynamic
        )
        result['transcript_id'] = transcript_id
        
        if run_id:
            db.log_pipeline_event(
                run_id=run_id,
                event_type='save_transcript',
                status='success',
                message=f'Transcript saved: {len(transcript)} chars',
                source_file=file_name
            )
        
        # Step 2: Create all meetings
        if meetings_data:
            logger.info(f"Creating {len(meetings_data)} meeting(s)...")
            for i, meeting_data in enumerate(meetings_data):
                try:
                    meeting_id, meeting_url = db.create_meeting(
                        meeting_data=meeting_data,
                        transcript=transcript,
                        duration=duration,
                        filename=f"{file_name} (Meeting {i+1})" if len(meetings_data) > 1 else file_name,
                        transcript_id=transcript_id
                    )
                    result['meeting_ids'].append(meeting_id)
                    result['meeting_urls'].append(meeting_url)
                    logger.info(f"Meeting {i+1} created: {meeting_id}")
                except Exception as e:
                    logger.error(f"Failed to create meeting {i+1}: {e}", exc_info=True)
        
        # Step 3: Create all reflections
        if reflections_data:
            logger.info(f"Creating {len(reflections_data)} reflection(s)...")
            for i, reflection_data in enumerate(reflections_data):
                try:
                    reflection_id, reflection_url = db.create_reflection(
                        reflection_data=reflection_data,
                        transcript=transcript,
                        duration=duration,
                        filename=f"{file_name} (Reflection {i+1})" if len(reflections_data) > 1 else file_name,
                        transcript_id=transcript_id
                    )
                    result['reflection_ids'].append(reflection_id)
                    result['reflection_urls'].append(reflection_url)
                    logger.info(f"Reflection {i+1} created: {reflection_id}")
                except Exception as e:
                    logger.error(f"Failed to create reflection {i+1}: {e}", exc_info=True)
        
        # NOTE: No fallback - let Intelligence Service handle all analysis
        # If nothing was created, that's intentional (e.g., short audio, silence)
        
        # Determine primary item for task linking
        if result['meeting_ids']:
            result['primary_type'] = 'meeting'
            result['primary_id'] = result['meeting_ids'][0]
        elif result['reflection_ids']:
            result['primary_type'] = 'reflection'
            result['primary_id'] = result['reflection_ids'][0]
        
        # Step 4: Create tasks (if any)
        if tasks_data and result['primary_id']:
            logger.info(f"Creating {len(tasks_data)} task(s)...")
            created_tasks = db.create_tasks(
                tasks_data=tasks_data,
                origin_id=result['primary_id'],
                origin_type=result['primary_type']
            )
            result['task_ids'] = [task_id for task_id, _ in created_tasks]
            result['task_urls'] = [task_url for _, task_url in created_tasks]
            logger.info(f"Created {len(created_tasks)} tasks")
        
        # Step 5: Update CRM entries (if any)
        if crm_updates:
            logger.info(f"Processing {len(crm_updates)} CRM update(s)...")
            meeting_id = result['meeting_ids'][0] if result['meeting_ids'] else None
            crm_ids = db.update_crm(
                crm_updates=crm_updates,
                meeting_id=meeting_id
            )
            result['crm_updated_ids'] = crm_ids
            logger.info(f"Updated {len(crm_ids)} CRM contacts")
        
        # Step 6: Link transcript to created items
        db.link_transcript_to_items(
            transcript_id=transcript_id,
            meeting_ids=result['meeting_ids'],
            reflection_ids=result['reflection_ids']
        )
        
        result['save_success'] = True
        
        # Log success
        total_items = len(result['meeting_ids']) + len(result['reflection_ids'])
        if run_id:
            db.log_pipeline_event(
                run_id=run_id,
                event_type='save_complete',
                status='success',
                message=f'Saved {total_items} item(s), {len(result["task_ids"])} task(s), {len(result["crm_updated_ids"])} CRM update(s)',
                source_file=file_name,
                details={
                    'meetings': len(result['meeting_ids']),
                    'reflections': len(result['reflection_ids']),
                    'tasks': len(result['task_ids']),
                    'crm_updates': len(result['crm_updated_ids'])
                }
            )
        
        logger.info(f"✓ Supabase save completed: {total_items} item(s), {len(result['task_ids'])} task(s), {len(result['crm_updated_ids'])} CRM update(s)")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in Supabase save task: {e}", exc_info=True)
        
        if run_id:
            db.log_pipeline_event(
                run_id=run_id,
                event_type='save_error',
                status='error',
                message=str(e),
                source_file=file_name
            )
        
        result['save_success'] = False
        return result
