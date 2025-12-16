"""
Multi-Database Notion Task: Save to Meetings, Reflections, Tasks, and CRM.
"""

import logging
from typing import Dict, Any
from src.config import Config
from src.notion.multi_db import NotionMultiDatabase

logger = logging.getLogger('Jarvis.Tasks.NotionMulti')

# Global Notion client
_notion_multi = None


def get_notion_multi() -> NotionMultiDatabase:
    """Get or create global Notion multi-database client."""
    global _notion_multi
    if _notion_multi is None:
        _notion_multi = NotionMultiDatabase(
            api_key=Config.NOTION_API_KEY,
            meeting_db_id=Config.NOTION_MEETING_DATABASE_ID,
            crm_db_id=Config.NOTION_CRM_DATABASE_ID,
            tasks_db_id=Config.NOTION_TASKS_DATABASE_ID,
            reflections_db_id=Config.NOTION_REFLECTIONS_DATABASE_ID
        )
    return _notion_multi


def save_to_notion_multi(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Save analyzed content to appropriate Notion databases.
    
    Input (from context):
        - primary_category: Main category (from analyze_multi task)
        - meetings: List of meeting data (from analyze_multi task)
        - reflections: List of reflection data (from analyze_multi task)
        - tasks: List of tasks (from analyze_multi task)
        - crm_updates: List of CRM updates (from analyze_multi task)
        - transcript: Full transcript (from transcribe task)
        - duration: Audio duration (from transcribe task)
        - file_name: Original filename (from download task)
    
    Output (to context):
        - meeting_ids: List of created meeting page IDs
        - meeting_urls: List of created meeting URLs
        - reflection_ids: List of created reflection page IDs
        - reflection_urls: List of created reflection URLs
        - task_ids: List of created task page IDs
        - task_urls: List of created task URLs
        - crm_ids: List of updated/created CRM page IDs
        - save_success: Boolean
    """
    logger.info("Starting multi-database Notion save task")
    
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
    file_name = download_result.get('file_name', 'unknown.m4a')
    
    # Get Notion client
    notion = get_notion_multi()
    
    result = {
        'meeting_ids': [],
        'meeting_urls': [],
        'reflection_ids': [],
        'reflection_urls': [],
        'task_ids': [],
        'task_urls': [],
        'crm_ids': [],
        'save_success': False
    }
    
    try:
        # Step 1: Create all meetings
        if meetings_data:
            logger.info(f"Creating {len(meetings_data)} meeting(s)...", extra={'meeting_count': len(meetings_data)})
            for i, meeting_data in enumerate(meetings_data):
                try:
                    page_id, page_url = notion.create_meeting(
                        meeting_data=meeting_data,
                        transcript=transcript,
                        duration=duration,
                        filename=f"{file_name} (Meeting {i+1})" if len(meetings_data) > 1 else file_name
                    )
                    result['meeting_ids'].append(page_id)
                    result['meeting_urls'].append(page_url)
                    logger.info(f"Meeting {i+1} created: {page_url}", extra={'page_id': page_id, 'meeting_index': i})
                except Exception as e:
                    logger.error(f"Failed to create meeting {i+1}: {e}", extra={'meeting_index': i, 'error': str(e)}, exc_info=True)
                    # Continue with other meetings even if one fails
        
        # Step 2: Create all reflections
        if reflections_data:
            logger.info(f"Creating {len(reflections_data)} reflection(s)...", extra={'reflection_count': len(reflections_data)})
            for i, reflection_data in enumerate(reflections_data):
                try:
                    page_id, page_url = notion.create_reflection(
                        reflection_data=reflection_data,
                        transcript=transcript,
                        duration=duration,
                        filename=f"{file_name} (Reflection {i+1})" if len(reflections_data) > 1 else file_name
                    )
                    result['reflection_ids'].append(page_id)
                    result['reflection_urls'].append(page_url)
                    logger.info(f"Reflection {i+1} created: {page_url}", extra={'page_id': page_id, 'reflection_index': i})
                except Exception as e:
                    logger.error(f"Failed to create reflection {i+1}: {e}", extra={'reflection_index': i, 'error': str(e)}, exc_info=True)
        
        # Fallback: If no meetings or reflections were created
        if not result['meeting_ids'] and not result['reflection_ids']:
            logger.warning(f"No meetings or reflections created for category '{primary_category}'")
            # Create a basic reflection as fallback
            fallback_reflection = {
                'title': file_name.replace('.mp3', '').replace('.m4a', '').replace('_', ' ')[:60],
                'date': None,
                'location': None,
                'tags': ['unprocessed', primary_category],
                'content': transcript[:1000]
            }
            page_id, page_url = notion.create_reflection(
                reflection_data=fallback_reflection,
                transcript=transcript,
                duration=duration,
                filename=file_name
            )
            result['reflection_ids'].append(page_id)
            result['reflection_urls'].append(page_url)
            logger.info(f"Fallback reflection created: {page_url}")
        
        # Step 3: Create tasks (if any)
        # Link tasks to first meeting or reflection created
        primary_page_id = (result['meeting_ids'] + result['reflection_ids'])[0] if (result['meeting_ids'] or result['reflection_ids']) else None
        primary_type = 'meeting' if result['meeting_ids'] else 'reflection'
        primary_page_url = (result['meeting_urls'] + result['reflection_urls'])[0] if (result['meeting_urls'] or result['reflection_urls']) else None
        
        # Store in result for logging
        result['primary_type'] = primary_type
        result['primary_page_url'] = primary_page_url
        
        if tasks_data and primary_page_id:
            logger.info(f"Creating {len(tasks_data)} tasks...")
            created_tasks = notion.create_tasks(
                tasks_data=tasks_data,
                origin_page_id=primary_page_id,
                origin_type=primary_type
            )
            
            result['task_ids'] = [task_id for task_id, _ in created_tasks]
            result['task_urls'] = [task_url for _, task_url in created_tasks]
            
            logger.info(f"Created {len(created_tasks)} tasks")
            
            # Link tasks back to origin page
            notion.update_origin_with_tasks(
                origin_page_id=primary_page_id,
                task_ids=result['task_ids'],
                origin_type=primary_type
            )
        
        # Step 4: Update/create CRM entries (if any)
        if crm_updates:
            logger.info(f"Processing {len(crm_updates)} CRM updates...")
            
            # Pass first meeting page ID if this was a meeting
            meeting_page_id = result['meeting_ids'][0] if result['meeting_ids'] else None
            
            crm_ids = notion.update_crm(
                crm_updates=crm_updates,
                meeting_page_id=meeting_page_id
            )
            
            result['crm_ids'] = crm_ids
            logger.info(f"Updated/created {len(crm_ids)} CRM entries")
        
        result['save_success'] = True
        total_pages = len(result['meeting_ids']) + len(result['reflection_ids'])
        logger.info(f"Multi-database save completed: {total_pages} page(s), {len(result['task_ids'])} task(s), {len(result['crm_ids'])} CRM update(s)")
        
        # Log summary
        logger.info(f"Summary:")
        if result.get('primary_page_url'):
            logger.info(f"  Primary: {result.get('primary_type', 'unknown')} → {result['primary_page_url']}")
        logger.info(f"  Tasks: {len(result['task_ids'])} created")
        logger.info(f"  CRM: {len(result['crm_ids'])} updated")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in multi-database save: {e}")
        result['save_success'] = False
        raise
