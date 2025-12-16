"""
Multi-Database Supabase Helper.
Handles creation and updates across Meetings, Reflections, Tasks, and Contacts.
Mirrors the functionality of notion/multi_db.py but writes to Supabase.
"""

import logging
import uuid
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone

from .client import supabase

logger = logging.getLogger('Jarvis.Supabase.Multi')


class SupabaseMultiDatabase:
    """Handle operations across multiple Supabase tables."""
    
    def __init__(self):
        self.client = supabase
        logger.info("Multi-database Supabase client initialized")
    
    # =========================================================================
    # PIPELINE LOGGING
    # =========================================================================
    
    def log_pipeline_event(
        self, 
        run_id: str,
        event_type: str,
        status: str,
        message: str,
        source_file: str = None,
        duration_ms: int = None,
        details: dict = None
    ) -> None:
        """
        Log a pipeline event to pipeline_logs table.
        
        Args:
            run_id: UUID grouping all events in a single pipeline run
            event_type: 'download', 'transcribe', 'analyze', 'save', 'complete', 'error'
            status: 'started', 'success', 'error', 'skipped'
            message: Human-readable message
            source_file: Original filename being processed
            duration_ms: How long this step took
            details: Any extra JSON data
        """
        try:
            payload = {
                "run_id": run_id,
                "event_type": event_type,
                "status": status,
                "message": message,
            }
            if source_file:
                payload["source_file"] = source_file
            if duration_ms is not None:
                payload["duration_ms"] = duration_ms
            if details:
                payload["details"] = details
            
            self.client.table("pipeline_logs").insert(payload).execute()
            logger.debug(f"[{event_type}] {status}: {message}")
        except Exception as e:
            logger.error(f"Failed to log pipeline event: {e}")
    
    # =========================================================================
    # CONTACT LOOKUP (for linking meetings to CRM)
    # =========================================================================
    
    def find_contact_by_name(self, name: str) -> Optional[Dict]:
        """
        Find a contact by name using fuzzy matching.
        Returns the contact dict if found, None otherwise.
        """
        if not name:
            return None
        
        try:
            # Split name into parts
            name_parts = name.strip().split()
            if not name_parts:
                return None
            
            first_name = name_parts[0]
            last_name = name_parts[-1] if len(name_parts) > 1 else None
            
            # Strategy 1: Exact full name match
            if last_name:
                result = self.client.table("contacts").select("*").ilike(
                    "first_name", first_name
                ).ilike(
                    "last_name", last_name
                ).is_("deleted_at", "null").execute()
                
                if result.data:
                    logger.info(f"Found contact by exact name: {name}")
                    return result.data[0]
            
            # Strategy 2: First name only (if unique)
            result = self.client.table("contacts").select("*").ilike(
                "first_name", first_name
            ).is_("deleted_at", "null").execute()
            
            if len(result.data) == 1:
                contact = result.data[0]
                logger.info(f"Found unique contact by first name '{first_name}': {contact.get('first_name')} {contact.get('last_name')}")
                return contact
            elif len(result.data) > 1:
                logger.info(f"Multiple contacts match first name '{first_name}', skipping auto-link")
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding contact '{name}': {e}")
            return None
    
    # =========================================================================
    # TRANSCRIPTS
    # =========================================================================
    
    def create_transcript(
        self,
        source_file: str,
        full_text: str,
        audio_duration_seconds: float = None,
        language: str = None,
        segments: List[Dict] = None,
        speakers: List[str] = None,
        model_used: str = None
    ) -> str:
        """
        Create a transcript record.
        
        Returns:
            transcript_id (UUID string)
        """
        try:
            payload = {
                "source_file": source_file,
                "full_text": full_text,
            }
            if audio_duration_seconds is not None:
                payload["audio_duration_seconds"] = audio_duration_seconds
            if language:
                payload["language"] = language
            if segments:
                payload["segments"] = segments
            if speakers:
                payload["speakers"] = speakers
            if model_used:
                payload["model_used"] = model_used
            
            result = self.client.table("transcripts").insert(payload).execute()
            transcript_id = result.data[0]["id"]
            logger.info(f"Transcript created: {transcript_id}")
            return transcript_id
            
        except Exception as e:
            logger.error(f"Error creating transcript: {e}")
            raise
    
    # =========================================================================
    # MEETINGS
    # =========================================================================
    
    def create_meeting(
        self,
        meeting_data: Dict,
        transcript: str,
        duration: float,
        filename: str,
        transcript_id: str = None
    ) -> Tuple[str, str]:
        """
        Create meeting entry in Supabase.
        
        Args:
            meeting_data: Meeting information from Claude analysis
            transcript: Full transcript text
            duration: Audio duration in seconds
            filename: Original filename
            transcript_id: Optional link to transcripts table
        
        Returns:
            Tuple of (meeting_id, "supabase://meetings/{id}")
        """
        try:
            title = meeting_data.get('title', 'Untitled Meeting')
            date = meeting_data.get('date')
            location = meeting_data.get('location')
            person_name = meeting_data.get('person_name')
            summary = meeting_data.get('summary', '')
            topics_discussed = meeting_data.get('topics_discussed', [])
            follow_ups = meeting_data.get('follow_up_conversation', [])
            people_mentioned = meeting_data.get('people_mentioned', [])
            key_points = meeting_data.get('key_points', [])  # Legacy support
            
            logger.info(f"Creating meeting: {title}")
            
            # Find contact by name
            contact_id = None
            if person_name:
                contact = self.find_contact_by_name(person_name)
                if contact:
                    contact_id = contact.get('id')
                    logger.info(f"Linked meeting to contact: {person_name} ({contact_id})")
            
            payload = {
                "title": title,
                "date": date,
                "location": location,
                "summary": summary,
                "topics_discussed": topics_discussed,
                "follow_up_items": follow_ups,
                "people_mentioned": people_mentioned,
                "key_points": key_points,
                "contact_id": contact_id,
                "contact_name": person_name,
                "source_file": filename,
                "audio_duration_seconds": duration,
            }
            
            if transcript_id:
                payload["transcript_id"] = transcript_id
            
            result = self.client.table("meetings").insert(payload).execute()
            meeting_id = result.data[0]["id"]
            meeting_url = f"supabase://meetings/{meeting_id}"
            
            logger.info(f"Meeting created: {meeting_id}")
            return meeting_id, meeting_url
            
        except Exception as e:
            logger.error(f"Error creating meeting: {e}")
            raise
    
    # =========================================================================
    # REFLECTIONS
    # =========================================================================
    
    def create_reflection(
        self,
        reflection_data: Dict,
        transcript: str,
        duration: float,
        filename: str,
        transcript_id: str = None
    ) -> Tuple[str, str]:
        """
        Create reflection entry in Supabase.
        
        Returns:
            Tuple of (reflection_id, "supabase://reflections/{id}")
        """
        try:
            title = reflection_data.get('title', 'Untitled Reflection')
            date = reflection_data.get('date')
            location = reflection_data.get('location')
            tags = reflection_data.get('tags', [])
            sections = reflection_data.get('sections', [])
            content = reflection_data.get('content', '')
            
            logger.info(f"Creating reflection: {title}")
            
            payload = {
                "title": title,
                "date": date,
                "location": location,
                "tags": tags,
                "sections": sections,
                "content": content,
                "source_file": filename,
                "audio_duration_seconds": duration,
            }
            
            if transcript_id:
                payload["transcript_id"] = transcript_id
            
            result = self.client.table("reflections").insert(payload).execute()
            reflection_id = result.data[0]["id"]
            reflection_url = f"supabase://reflections/{reflection_id}"
            
            logger.info(f"Reflection created: {reflection_id}")
            return reflection_id, reflection_url
            
        except Exception as e:
            logger.error(f"Error creating reflection: {e}")
            raise
    
    # =========================================================================
    # TASKS
    # =========================================================================
    
    def create_tasks(
        self,
        tasks_data: List[Dict],
        origin_id: str,
        origin_type: str
    ) -> List[Tuple[str, str]]:
        """
        Create task entries in Supabase.
        
        Args:
            tasks_data: List of task dicts from Claude
            origin_id: ID of the meeting/reflection that generated these tasks
            origin_type: 'meeting' or 'reflection'
        
        Returns:
            List of tuples (task_id, task_url) for created tasks
        """
        created_tasks = []
        
        for task in tasks_data:
            try:
                title = task.get('title', 'Untitled Task')
                description = task.get('description', '')
                due_date = task.get('due_date')
                priority = task.get('priority', 'medium')
                
                # Validate priority
                if priority not in ('high', 'medium', 'low'):
                    priority = 'medium'
                
                payload = {
                    "title": title,
                    "description": description,
                    "due_date": due_date,
                    "priority": priority,
                    "status": "pending",
                    "origin_type": origin_type,
                    "origin_id": origin_id,
                }
                
                result = self.client.table("tasks").insert(payload).execute()
                task_id = result.data[0]["id"]
                task_url = f"supabase://tasks/{task_id}"
                
                created_tasks.append((task_id, task_url))
                logger.info(f"Task created: {title}")
                
            except Exception as e:
                logger.error(f"Error creating task '{task.get('title', 'unknown')}': {e}")
        
        return created_tasks
    
    # =========================================================================
    # CRM UPDATES
    # =========================================================================
    
    def update_crm(
        self,
        crm_updates: List[Dict],
        meeting_id: str = None
    ) -> List[str]:
        """
        Update contact information based on CRM updates from transcript.
        
        Note: This updates EXISTING contacts only - doesn't create new ones.
        Creating contacts should be done through jarvis-backend sync.
        
        Args:
            crm_updates: List of update dicts from Claude
            meeting_id: Optional meeting ID to link
        
        Returns:
            List of updated contact IDs
        """
        updated_ids = []
        
        for update in crm_updates:
            try:
                person_name = update.get('person_name')
                if not person_name:
                    continue
                
                # Find the contact
                contact = self.find_contact_by_name(person_name)
                if not contact:
                    logger.info(f"Contact not found for CRM update: {person_name}")
                    continue
                
                contact_id = contact['id']
                
                # Build update payload with only non-null fields
                update_payload = {}
                
                # Map CRM update fields to contact columns
                field_mapping = {
                    'company': 'company',
                    'job_title': 'job_title',
                    'location': 'location',
                    'notes': 'notes',  # Append to existing notes
                    'email': 'email',
                    'phone': 'phone',
                }
                
                for update_field, db_field in field_mapping.items():
                    value = update.get(update_field)
                    if value:
                        if db_field == 'notes':
                            # Append to existing notes
                            existing_notes = contact.get('notes', '') or ''
                            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                            new_note = f"\n[{timestamp}] {value}"
                            update_payload['notes'] = existing_notes + new_note
                        else:
                            update_payload[db_field] = value
                
                if update_payload:
                    update_payload['updated_at'] = datetime.now(timezone.utc).isoformat()
                    update_payload['last_sync_source'] = 'audio_pipeline'
                    
                    self.client.table("contacts").update(
                        update_payload
                    ).eq("id", contact_id).execute()
                    
                    updated_ids.append(contact_id)
                    logger.info(f"Updated contact {person_name}: {list(update_payload.keys())}")
                
            except Exception as e:
                logger.error(f"Error updating CRM for '{update.get('person_name', 'unknown')}': {e}")
        
        return updated_ids
    
    # =========================================================================
    # UTILITY: Link transcript to created items
    # =========================================================================
    
    def link_transcript_to_items(
        self,
        transcript_id: str,
        meeting_ids: List[str] = None,
        reflection_ids: List[str] = None
    ) -> None:
        """Update transcript record with linked meeting/reflection IDs."""
        try:
            payload = {}
            if meeting_ids:
                payload["meeting_ids"] = meeting_ids
            if reflection_ids:
                payload["reflection_ids"] = reflection_ids
            
            if payload:
                self.client.table("transcripts").update(
                    payload
                ).eq("id", transcript_id).execute()
                logger.debug(f"Linked transcript {transcript_id} to items")
                
        except Exception as e:
            logger.error(f"Error linking transcript to items: {e}")
