"""
Multi-Database Notion Helper.
Handles creation and updates across Meetings, Reflections, Tasks, and CRM databases.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from notion_client import Client

logger = logging.getLogger('Jarvis.Notion.Multi')


class NotionMultiDatabase:
    """Handle operations across multiple Notion databases."""
    
    def __init__(self, api_key: str, meeting_db_id: str, crm_db_id: str, 
                 tasks_db_id: str, reflections_db_id: str):
        self.client = Client(auth=api_key, notion_version="2025-09-03")
        self.meeting_db_id = meeting_db_id
        self.crm_db_id = crm_db_id
        self.tasks_db_id = tasks_db_id
        self.reflections_db_id = reflections_db_id
        logger.info("Multi-database Notion client initialized")
    
    def create_meeting(self, meeting_data: Dict, transcript: str, 
                      duration: float, filename: str) -> Tuple[str, str]:
        """
        Create meeting entry in Notion.
        
        Args:
            meeting_data: Meeting information from Claude
            transcript: Full transcript
            duration: Audio duration in seconds
            filename: Original filename
        
        Returns:
            Tuple of (page_id, page_url)
        """
        try:
            title = meeting_data.get('title', 'Untitled Meeting')
            date = meeting_data.get('date')
            location = meeting_data.get('location')
            person_name = meeting_data.get('person_name')
            summary = meeting_data.get('summary', '')
            # Support both old format (key_points, topics) and new format (topics_discussed)
            topics_discussed = meeting_data.get('topics_discussed', [])
            follow_ups = meeting_data.get('follow_up_conversation', [])
            people_mentioned = meeting_data.get('people_mentioned', [])
            # Legacy support
            key_points = meeting_data.get('key_points', [])
            topics = meeting_data.get('topics', [])
            
            logger.info(f"Creating meeting: {title}")
            
            # Build properties
            properties = {
                'Meeting': {
                    'title': [{'text': {'content': title}}]
                },
                'Date': {
                    'date': {'start': date} if date else None
                }
            }
            
            # Add location if provided
            if location:
                properties['Location'] = {
                    'rich_text': [{'text': {'content': location}}]
                }
            
            # Link to CRM person if name provided (but not specified to create)
            if person_name:
                person_page_id = self._find_person_in_crm(person_name)
                if person_page_id:
                    properties['Person'] = {'relation': [{'id': person_page_id}]}
                    logger.info(f"Linked meeting to CRM contact: {person_name}")
                else:
                    logger.info(f"Person '{person_name}' not found in CRM, not linking")
            
            # Build page content with new structured format
            content_blocks = self._build_meeting_content(
                summary=summary,
                topics_discussed=topics_discussed,
                follow_ups=follow_ups,
                people_mentioned=people_mentioned,
                transcript=transcript,
                duration=duration,
                filename=filename,
                # Legacy support
                key_points=key_points,
                topics=topics
            )
            
            # Create the page with icon
            response = self.client.pages.create(
                parent={'database_id': self.meeting_db_id},
                icon={'emoji': '🤝'},  # Default meeting icon
                properties=properties,
                children=content_blocks
            )
            
            page_id = response['id']
            page_url = response['url']
            
            logger.info(f"Meeting created: {page_url}")
            return page_id, page_url
            
        except Exception as e:
            logger.error(f"Error creating meeting: {e}")
            raise
    
    def create_reflection(self, reflection_data: Dict, transcript: str,
                         duration: float, filename: str) -> Tuple[str, str]:
        """
        Create reflection entry in Notion.
        
        Returns:
            Tuple of (page_id, page_url)
        """
        try:
            title = reflection_data.get('title', 'Untitled Reflection')
            date = reflection_data.get('date')
            location = reflection_data.get('location')
            tags = reflection_data.get('tags', [])
            # Support both old format (content) and new format (sections)
            sections = reflection_data.get('sections', [])
            content = reflection_data.get('content', '')
            
            logger.info(f"Creating reflection: {title}")
            
            # Build properties
            properties = {
                'Name': {
                    'title': [{'text': {'content': title}}]
                },
                'Date': {
                    'date': {'start': date} if date else None
                }
            }
            
            # Add location if provided
            if location:
                properties['Location'] = {
                    'rich_text': [{'text': {'content': location}}]
                }
            
            # Add tags (limit to 1-3 as per new format)
            if tags:
                properties['Tags'] = {
                    'multi_select': [{'name': tag} for tag in tags[:3]]  # Limit to 3
                }
            
            # Build page content with new structured format
            content_blocks = self._build_reflection_content(
                sections=sections,
                content=content,
                transcript=transcript,
                duration=duration,
                filename=filename
            )
            
            # Create the page with icon
            response = self.client.pages.create(
                parent={'database_id': self.reflections_db_id},
                icon={'emoji': '💭'},  # Default reflection icon
                properties=properties,
                children=content_blocks
            )
            
            page_id = response['id']
            page_url = response['url']
            
            logger.info(f"Reflection created: {page_url}")
            return page_id, page_url
            
        except Exception as e:
            logger.error(f"Error creating reflection: {e}")
            raise
    
    def create_tasks(self, tasks_data: List[Dict], origin_page_id: str,
                    origin_type: str) -> List[Tuple[str, str]]:
        """
        Create task entries in Notion.
        
        Args:
            tasks_data: List of task dicts from Claude
            origin_page_id: ID of the meeting/reflection that generated these tasks
            origin_type: 'meeting' or 'reflection'
        
        Returns:
            List of tuples (page_id, page_url) for created tasks
        """
        created_tasks = []
        
        for task in tasks_data:
            try:
                title = task.get('title', 'Untitled Task')
                description = task.get('description', '')
                due_date = task.get('due_date')
                
                logger.info(f"Creating task: {title}")
                
                # Build properties
                properties = {
                    'Name': {
                        'title': [{'text': {'content': title}}]
                    },
                    'Status': {
                        'status': {'name': 'Not started'}
                    }
                }
                
                # Add due date if provided
                if due_date:
                    properties['Due'] = {
                        'date': {'start': due_date}
                    }
                
                # Link back to origin (Meeting or Reflection)
                if origin_type == 'meeting':
                    properties['Origin2'] = {'relation': [{'id': origin_page_id}]}
                elif origin_type == 'reflection':
                    properties['Origin1'] = {'relation': [{'id': origin_page_id}]}
                
                # Build page content
                content_blocks = []
                if description:
                    content_blocks.append({
                        'object': 'block',
                        'type': 'paragraph',
                        'paragraph': {
                            'rich_text': [{'text': {'content': description}}]
                        }
                    })
                
                # Create the task with icon
                response = self.client.pages.create(
                    parent={'database_id': self.tasks_db_id},
                    icon={'emoji': '✅'},  # Default task icon
                    properties=properties,
                    children=content_blocks if content_blocks else None
                )
                
                page_id = response['id']
                page_url = response['url']
                created_tasks.append((page_id, page_url))
                
                logger.info(f"Task created: {page_url}")
                
            except Exception as e:
                logger.error(f"Error creating task '{task.get('title')}': {e}")
                # Continue with other tasks even if one fails
        
        return created_tasks
    
    def update_origin_with_tasks(self, origin_page_id: str, task_ids: List[str],
                                origin_type: str):
        """Update meeting/reflection with links to created tasks."""
        try:
            if not task_ids:
                return
            
            # Property name differs based on origin type
            relation_property = 'Resulting Tasks'
            
            self.client.pages.update(
                page_id=origin_page_id,
                properties={
                    relation_property: {
                        'relation': [{'id': task_id} for task_id in task_ids]
                    }
                }
            )
            
            logger.info(f"Updated {origin_type} with {len(task_ids)} task links")
            
        except Exception as e:
            logger.error(f"Error linking tasks to {origin_type}: {e}")
    
    def update_crm(self, crm_updates: List[Dict], meeting_page_id: Optional[str] = None) -> List[str]:
        """
        Update or create CRM entries.
        
        Args:
            crm_updates: List of CRM update dicts from Claude
            meeting_page_id: Optional meeting page to link to
        
        Returns:
            List of CRM page IDs that were updated/created
        """
        updated_crm_ids = []
        
        for crm_data in crm_updates:
            try:
                person_name = crm_data.get('person_name')
                create_if_missing = crm_data.get('create_if_missing', False)
                updates = crm_data.get('updates', {})
                
                if not person_name:
                    logger.warning("CRM update missing person_name, skipping")
                    continue
                
                logger.info(f"Processing CRM update for: {person_name}")
                
                # Find existing person
                person_page_id = self._find_person_in_crm(person_name)
                
                if person_page_id:
                    # Update existing person
                    self._update_crm_entry(person_page_id, updates, meeting_page_id)
                    updated_crm_ids.append(person_page_id)
                elif create_if_missing:
                    # Create new person
                    person_page_id = self._create_crm_entry(person_name, updates, meeting_page_id)
                    updated_crm_ids.append(person_page_id)
                    logger.info(f"Created new CRM entry for: {person_name}")
                else:
                    logger.info(f"Person '{person_name}' not found and create_if_missing=False, skipping")
                
            except Exception as e:
                logger.error(f"Error processing CRM update for '{crm_data.get('person_name')}': {e}")
        
        return updated_crm_ids
    
    def _find_person_in_crm(self, person_name: str) -> Optional[str]:
        """
        Search CRM database for a person by name with intelligent matching.
        
        Matches:
        - Exact match: "Paul Beckers" finds "Paul Beckers"
        - First name only: "Paul" finds "Paul Beckers" (if only one Paul exists)
        - Last name only: "Beckers" finds "Paul Beckers" (if only one Beckers exists)
        - Partial match: "Paul B" finds "Paul Beckers"
        """
        try:
            search_name = person_name.strip().lower()
            
            # First, try to get all contacts (for smart matching)
            all_results = self.client.databases.query(
                database_id=self.crm_db_id,
                page_size=100  # Get up to 100 contacts
            )
            
            if not all_results['results']:
                return None
            
            # Extract names from results
            matches = []
            for result in all_results['results']:
                try:
                    title_prop = result['properties'].get('Name', {})
                    if title_prop.get('title'):
                        full_name = title_prop['title'][0]['text']['content']
                        full_name_lower = full_name.lower()
                        
                        # Check various matching strategies
                        match_score = self._calculate_name_match_score(search_name, full_name_lower)
                        
                        if match_score > 0:
                            matches.append({
                                'id': result['id'],
                                'name': full_name,
                                'score': match_score
                            })
                except (KeyError, IndexError) as e:
                    continue
            
            if not matches:
                return None
            
            # Sort by match score (highest first)
            matches.sort(key=lambda x: x['score'], reverse=True)
            
            # If top match is significantly better (exact or first name only match), use it
            best_match = matches[0]
            
            # Log the match for transparency
            if best_match['score'] >= 90:  # Exact or very close match
                logger.info(f"CRM: Matched '{person_name}' → '{best_match['name']}' (exact/close match)")
                return best_match['id']
            elif best_match['score'] >= 70 and (len(matches) == 1 or matches[0]['score'] > matches[1]['score'] * 1.5):
                # Good match and clearly the best option
                logger.info(f"CRM: Matched '{person_name}' → '{best_match['name']}' (confident match)")
                return best_match['id']
            elif len(matches) == 1:
                # Only one person matches at all
                logger.info(f"CRM: Matched '{person_name}' → '{best_match['name']}' (only match)")
                return best_match['id']
            else:
                # Ambiguous - multiple similar matches
                logger.warning(f"CRM: Ambiguous match for '{person_name}': found {len(matches)} similar names, not linking")
                return None
            
        except Exception as e:
            logger.error(f"Error searching CRM for '{person_name}': {e}")
            return None
    
    def _calculate_name_match_score(self, search_name: str, full_name: str) -> int:
        """
        Calculate how well a search name matches a full name.
        Returns score 0-100 (higher = better match).
        """
        # Exact match
        if search_name == full_name:
            return 100
        
        # Exact match ignoring case already handled by lowercase
        
        # Full name contains search exactly
        if search_name in full_name:
            return 90
        
        name_parts = full_name.split()
        search_parts = search_name.split()
        
        # Search is first name only and matches
        if len(search_parts) == 1 and search_parts[0] == name_parts[0]:
            return 85
        
        # Search is last name only and matches
        if len(search_parts) == 1 and len(name_parts) > 1 and search_parts[0] == name_parts[-1]:
            return 85
        
        # First name matches and search starts with last name initial
        if len(search_parts) == 2 and len(name_parts) >= 2:
            if search_parts[0] == name_parts[0] and name_parts[-1].startswith(search_parts[1]):
                return 80
        
        # All search parts found in full name
        if all(part in full_name for part in search_parts):
            return 70
        
        # First name starts with search
        if name_parts[0].startswith(search_name):
            return 60
        
        # Any name part starts with search
        if any(part.startswith(search_name) for part in name_parts):
            return 50
        
        # Partial overlap
        overlap = sum(1 for part in search_parts if any(part in name_part for name_part in name_parts))
        if overlap > 0:
            return 30 * overlap
        
        return 0
    
    def _create_crm_entry(self, person_name: str, updates: Dict,
                         meeting_page_id: Optional[str] = None) -> str:
        """Create a new CRM entry."""
        properties = {
            'Name': {
                'title': [{'text': {'content': person_name}}]
            }
        }
        
        # Add properties if provided
        if updates.get('company'):
            properties['Company'] = {
                'rich_text': [{'text': {'content': updates['company']}}]
            }
        
        if updates.get('position'):
            properties['Position'] = {
                'rich_text': [{'text': {'content': updates['position']}}]
            }
        
        if updates.get('location'):
            properties['Location'] = {
                'select': {'name': updates['location']}
            }
        
        if updates.get('birthday'):
            properties['Birthday'] = {
                'date': {'start': updates['birthday']}
            }
        
        # Link to meeting if provided
        if meeting_page_id:
            properties['Meeting'] = {
                'relation': [{'id': meeting_page_id}]
            }
        
        # Build page content with personal notes
        content_blocks = []
        if updates.get('personal_notes'):
            content_blocks.extend([
                {
                    'object': 'block',
                    'type': 'heading_3',
                    'heading_3': {
                        'rich_text': [{'text': {'content': 'Personal Notes'}}]
                    }
                },
                {
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': [{'text': {'content': updates['personal_notes']}}]
                    }
                }
            ])
        
        response = self.client.pages.create(
            parent={'database_id': self.crm_db_id},
            icon={'emoji': '👤'},  # Default CRM/person icon
            properties=properties,
            children=content_blocks if content_blocks else None
        )
        
        return response['id']
    
    def _update_crm_entry(self, person_page_id: str, updates: Dict,
                         meeting_page_id: Optional[str] = None):
        """Update an existing CRM entry."""
        # Update properties if provided
        properties = {}
        
        if updates.get('company'):
            properties['Company'] = {
                'rich_text': [{'text': {'content': updates['company']}}]
            }
        
        if updates.get('position'):
            properties['Position'] = {
                'rich_text': [{'text': {'content': updates['position']}}]
            }
        
        if updates.get('location'):
            properties['Location'] = {
                'select': {'name': updates['location']}
            }
        
        if updates.get('birthday'):
            properties['Birthday'] = {
                'date': {'start': updates['birthday']}
            }
        
        # Link to meeting if provided (append to existing relations)
        if meeting_page_id:
            # Get current relations
            page = self.client.pages.retrieve(page_id=person_page_id)
            existing_meetings = page['properties']['Meeting'].get('relation', [])
            meeting_ids = [m['id'] for m in existing_meetings]
            
            # Add new meeting if not already linked
            if meeting_page_id not in meeting_ids:
                meeting_ids.append(meeting_page_id)
                properties['Meeting'] = {
                    'relation': [{'id': mid} for mid in meeting_ids]
                }
        
        # Update properties if any
        if properties:
            self.client.pages.update(
                page_id=person_page_id,
                properties=properties
            )
        
        # Append personal notes to page content if provided
        if updates.get('personal_notes'):
            timestamp = datetime.now().strftime('%Y-%m-%d')
            self.client.blocks.children.append(
                block_id=person_page_id,
                children=[
                    {
                        'object': 'block',
                        'type': 'paragraph',
                        'paragraph': {
                            'rich_text': [
                                {'text': {'content': f'[{timestamp}] ', 'link': None},
                                 'annotations': {'bold': True}},
                                {'text': {'content': updates['personal_notes']}}
                            ]
                        }
                    }
                ]
            )
    
    def _build_meeting_content(self, summary: str, topics_discussed: List[Dict] = None,
                              follow_ups: List[Dict] = None, people_mentioned: List[str] = None,
                              transcript: str = '', duration: float = 0, filename: str = '',
                              key_points: List[str] = None, topics: List[str] = None) -> List[Dict]:
        """Build Notion blocks for meeting page content with structured topics and follow-ups."""
        blocks = []
        
        # Summary section
        if summary:
            blocks.extend([
                {
                    'object': 'block',
                    'type': 'heading_2',
                    'heading_2': {
                        'rich_text': [{'text': {'content': '📋 Summary'}}]
                    }
                },
                {
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': [{'text': {'content': summary}}]
                    }
                }
            ])
        
        # Topics Discussed section (new structured format)
        if topics_discussed:
            blocks.append({
                'object': 'block',
                'type': 'heading_2',
                'heading_2': {
                    'rich_text': [{'text': {'content': '💬 Topics Discussed'}}]
                }
            })
            
            for topic_obj in topics_discussed:
                topic_name = topic_obj.get('topic', 'Topic')
                details = topic_obj.get('details', [])
                
                # Topic as a toggle with details inside
                blocks.append({
                    'object': 'block',
                    'type': 'toggle',
                    'toggle': {
                        'rich_text': [{'text': {'content': f'📌 {topic_name}'}}],
                        'children': [
                            {
                                'object': 'block',
                                'type': 'bulleted_list_item',
                                'bulleted_list_item': {
                                    'rich_text': [{'text': {'content': detail}}]
                                }
                            } for detail in details
                        ] if details else [
                            {
                                'object': 'block',
                                'type': 'paragraph',
                                'paragraph': {
                                    'rich_text': [{'text': {'content': 'No details available'}}]
                                }
                            }
                        ]
                    }
                })
        
        # Legacy key_points support (fallback if no topics_discussed)
        elif key_points:
            blocks.append({
                'object': 'block',
                'type': 'heading_2',
                'heading_2': {
                    'rich_text': [{'text': {'content': 'Key Points'}}]
                }
            })
            
            for point in key_points:
                blocks.append({
                    'object': 'block',
                    'type': 'bulleted_list_item',
                    'bulleted_list_item': {
                        'rich_text': [{'text': {'content': point}}]
                    }
                })
        
        # Follow-ups section (for next conversation)
        if follow_ups:
            blocks.append({
                'object': 'block',
                'type': 'heading_2',
                'heading_2': {
                    'rich_text': [{'text': {'content': '🔮 Follow Up Next Time'}}]
                }
            })
            
            for follow_up in follow_ups:
                topic = follow_up.get('topic', '')
                context = follow_up.get('context', '')
                date_info = follow_up.get('date_if_known')
                
                # Build follow-up text
                follow_text = f"**{topic}**"
                if context:
                    follow_text = f"{topic}"
                
                blocks.append({
                    'object': 'block',
                    'type': 'bulleted_list_item',
                    'bulleted_list_item': {
                        'rich_text': [
                            {'text': {'content': topic}, 'annotations': {'bold': True}},
                            {'text': {'content': f' — {context}' if context else ''}}
                        ]
                    }
                })
                
                if date_info:
                    blocks.append({
                        'object': 'block',
                        'type': 'paragraph',
                        'paragraph': {
                            'rich_text': [{'text': {'content': f'    📅 {date_info}'}}]
                        }
                    })
        
        # People Mentioned section
        if people_mentioned and len(people_mentioned) > 0:
            blocks.append({
                'object': 'block',
                'type': 'heading_2',
                'heading_2': {
                    'rich_text': [{'text': {'content': '👥 People Mentioned'}}]
                }
            })
            
            blocks.append({
                'object': 'block',
                'type': 'paragraph',
                'paragraph': {
                    'rich_text': [{'text': {'content': ', '.join(people_mentioned)}}]
                }
            })
        
        # Full transcript in a toggle
        if transcript:
            blocks.extend([
                {
                    'object': 'block',
                    'type': 'heading_2',
                    'heading_2': {
                        'rich_text': [{'text': {'content': '📝 Full Transcript'}}]
                    }
                },
                {
                    'object': 'block',
                    'type': 'toggle',
                    'toggle': {
                        'rich_text': [{'text': {'content': 'Click to expand transcript'}}],
                        'children': [
                            {
                                'object': 'block',
                                'type': 'paragraph',
                                'paragraph': {
                                    'rich_text': [{'text': {'content': transcript[:2000]}}]
                                }
                            }
                        ]
                    }
                }
            ])
        
        # Metadata callout
        duration_min = round(duration / 60, 1) if duration else 0
        blocks.append({
            'object': 'block',
            'type': 'callout',
            'callout': {
                'rich_text': [
                    {'text': {'content': f'📎 {filename} • ⏱️ {duration_min} min'}}
                ],
                'icon': {'emoji': '🎙️'}
            }
        })
        
        return blocks
    
    def _build_reflection_content(self, sections: List[Dict] = None, content: str = '',
                                  transcript: str = '', duration: float = 0,
                                  filename: str = '') -> List[Dict]:
        """Build Notion blocks for reflection page content with structured sections."""
        blocks = []
        
        # New structured sections format
        if sections:
            for section in sections:
                heading = section.get('heading', 'Section')
                section_content = section.get('content', '')
                
                # Section heading
                blocks.append({
                    'object': 'block',
                    'type': 'heading_2',
                    'heading_2': {
                        'rich_text': [{'text': {'content': f'💡 {heading}'}}]
                    }
                })
                
                # Section content
                if section_content:
                    blocks.append({
                        'object': 'block',
                        'type': 'paragraph',
                        'paragraph': {
                            'rich_text': [{'text': {'content': section_content}}]
                        }
                    })
        
        # Legacy content support (fallback if no sections)
        elif content:
            blocks.extend([
                {
                    'object': 'block',
                    'type': 'heading_2',
                    'heading_2': {
                        'rich_text': [{'text': {'content': '💡 Reflection'}}]
                    }
                },
                {
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': [{'text': {'content': content}}]
                    }
                }
            ])
        
        # Full transcript in toggle
        if transcript:
            blocks.extend([
                {
                    'object': 'block',
                    'type': 'heading_2',
                    'heading_2': {
                        'rich_text': [{'text': {'content': '📝 Full Transcript'}}]
                    }
                },
                {
                    'object': 'block',
                    'type': 'toggle',
                    'toggle': {
                        'rich_text': [{'text': {'content': 'Click to expand transcript'}}],
                        'children': [
                            {
                                'object': 'block',
                                'type': 'paragraph',
                                'paragraph': {
                                    'rich_text': [{'text': {'content': transcript[:2000]}}]
                                }
                            }
                        ]
                    }
                }
            ])
        
        # Metadata callout
        duration_min = round(duration / 60, 1) if duration else 0
        blocks.append({
            'object': 'block',
            'type': 'callout',
            'callout': {
                'rich_text': [
                    {'text': {'content': f'📎 {filename} • ⏱️ {duration_min} min'}}
                ],
                'icon': {'emoji': '💭'}
            }
        })
        
        return blocks
