"""
Notion Task: Save processed data to Notion (Meeting Database or Other page).
"""

import logging
from typing import Dict, Any
import os
from notion_client import Client as NotionClient

logger = logging.getLogger('Jarvis.Tasks.Notion')

# Global Notion client instance
_notion_client = None


def get_notion_client() -> NotionClient:
    """Get or create global Notion client instance."""
    global _notion_client
    if _notion_client is None:
        api_key = os.getenv('NOTION_API_KEY')
        if not api_key:
            raise ValueError("NOTION_API_KEY not found in environment")
        _notion_client = NotionClient(
            auth=api_key,
            notion_version="2025-09-03"
        )
    return _notion_client


def save_to_notion(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Save all processed data to Notion.
    Routes to Meeting Database if is_meeting=True, otherwise to Other page.
    
    Input (from context):
        - is_meeting: Boolean (from analyze task)
        - title: Generated title (from analyze task)  
        - summary, key_points, action_items, people_mentioned, topics (from analyze task)
        - text: Full transcript (from transcribe task)
        - duration: Audio duration (from transcribe task)
        - file_name: Original filename (from download task)
    
    Output (to context):
        - notion_page_id: ID of created Notion page
        - notion_url: URL to Notion page
        - destination: "Meeting Database" or "Other"
    """
    logger.info("Starting Notion save task")
    
    # Get results from previous tasks
    analyze_result = context['task_results'].get('analyze_transcript', {})
    transcribe_result = context['task_results'].get('transcribe_audio', {})
    download_result = context['task_results'].get('download_audio_file', {})
    monitor_result = context['task_results'].get('monitor_google_drive', {})
    
    is_meeting = analyze_result.get('is_meeting', False)
    person_name = analyze_result.get('person')
    location = analyze_result.get('location')
    title = analyze_result.get('title', 'Untitled')
    summary = analyze_result.get('summary', '')
    key_points = analyze_result.get('key_points', [])
    action_items = analyze_result.get('action_items', [])
    people_mentioned = analyze_result.get('people_mentioned', [])
    topics = analyze_result.get('topics', [])
    
    transcript = transcribe_result.get('text', '')
    duration = transcribe_result.get('duration', 0)
    file_name = download_result.get('file_name', 'unknown.m4a')
    
    # Get file date from metadata
    file_metadata = monitor_result.get('file_metadata', {})
    modified_time = file_metadata.get('modifiedTime')
    
    # Convert to date string (YYYY-MM-DD)
    from datetime import datetime
    if modified_time:
        try:
            file_date = datetime.fromisoformat(modified_time.replace('Z', '+00:00')).date().isoformat()
        except (ValueError, AttributeError):
            file_date = datetime.now().date().isoformat()
    else:
        file_date = datetime.now().date().isoformat()
    
    # Get Notion client
    notion = get_notion_client()
    
    # Determine destination and create page
    if is_meeting:
        # Save to Meeting Database
        data_source_id = os.getenv('NOTION_MEETING_DATA_SOURCE_ID')
        if not data_source_id:
            raise ValueError("NOTION_MEETING_DATA_SOURCE_ID not configured")
        
        destination = "Meeting Database"
        logger.info(f"→ Routing to {destination}")
        
        # Try to find person in CRM database
        person_page_id = None
        if person_name:
            person_page_id = _find_person_in_crm(notion, person_name)
            if person_page_id:
                logger.info(f"  ✓ Found {person_name} in CRM: {person_page_id}")
            else:
                logger.info(f"  ⚠ {person_name} not found in CRM")
        
        # Build properties for Meeting database
        properties = {
            "Meeting": {
                "title": [{"text": {"content": person_name or title}}]
            },
            "Date": {
                "date": {"start": file_date}
            }
        }
        
        # Add Location if provided
        if location:
            properties["Location"] = {
                "rich_text": [{"text": {"content": location}}]
            }
        
        # Add Person relation if found in CRM
        if person_page_id:
            properties["Person"] = {
                "relation": [{"id": person_page_id}]
            }
        
        # Create page in database (data source parent)
        new_page = notion.pages.create(
            parent={"type": "data_source_id", "data_source_id": data_source_id},
            properties=properties,
            children=_build_page_content(
                summary, key_points, action_items, people_mentioned, topics, transcript, duration, file_name
            )
        )
    else:
        # Save to Other page
        other_page_id = os.getenv('NOTION_OTHER_PAGE_ID')
        if not other_page_id:
            raise ValueError("NOTION_OTHER_PAGE_ID not configured")
        
        destination = "Other"
        logger.info(f"→ Routing to {destination}")
        
        # Create page under Other
        new_page = notion.pages.create(
            parent={"type": "page_id", "page_id": other_page_id},
            properties={
                "title": {
                    "title": [{"text": {"content": title}}]
                }
            },
            children=_build_page_content(
                summary, key_points, action_items, people_mentioned, topics, transcript, duration, file_name
            )
        )
    
    page_id = new_page.get('id')
    page_url = new_page.get('url')
    
    logger.info(f"✓ Page created in {destination}")
    logger.info(f"  URL: {page_url}")
    
    return {
        'notion_page_id': page_id,
        'notion_url': page_url,
        'destination': destination
    }


def _find_person_in_crm(notion: NotionClient, person_name: str) -> str:
    """
    Search CRM database for a person by name.
    Returns the page ID if found, None otherwise.
    """
    crm_data_source_id = os.getenv('NOTION_CRM_DATA_SOURCE_ID')
    if not crm_data_source_id:
        logger.warning("NOTION_CRM_DATA_SOURCE_ID not configured")
        return None
    
    try:
        # Query CRM database using the data_sources API
        import requests
        api_key = os.getenv('NOTION_API_KEY')
        
        response = requests.post(
            f"https://api.notion.com/v1/data_sources/{crm_data_source_id}/query",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": "2025-09-03",
                "Content-Type": "application/json"
            },
            json={
                "filter": {
                    "property": "Name",
                    "title": {
                        "contains": person_name
                    }
                }
            }
        )
        
        if response.status_code == 200:
            results = response.json()
            pages = results.get('results', [])
            
            if pages:
                # Get exact match or first result
                for page in pages:
                    title_prop = page.get('properties', {}).get('Name', {})
                    if title_prop.get('type') == 'title':
                        title_list = title_prop.get('title', [])
                        if title_list:
                            name_text = title_list[0].get('plain_text', '')
                            if name_text.lower() == person_name.lower():
                                return page['id']
                # If no exact match, return first result
                return pages[0]['id']
        else:
            logger.error(f"CRM query failed: {response.status_code} - {response.text}")
        
        return None
        
    except Exception as e:
        logger.error(f"Error searching CRM for {person_name}: {e}")
        return None


def _build_page_content(summary, key_points, action_items, people_mentioned, topics, transcript, duration, file_name):
    """Build the content blocks for the Notion page."""
    
    blocks = []
    
    # Summary section
    if summary:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "📝 Summary"}}]}
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": summary}}]}
        })
    
    # Key Points
    if key_points:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "💡 Key Points"}}]}
        })
        for point in key_points:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"text": {"content": point}}]}
            })
    
    # Action Items
    if action_items:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "✅ Action Items"}}]}
        })
        for item in action_items:
            blocks.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"text": {"content": item}}],
                    "checked": False
                }
            })
    
    # People Mentioned
    if people_mentioned:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "👥 People Mentioned"}}]}
        })
        for person in people_mentioned:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"text": {"content": person}}]}
            })
    
    # Topics/Tags
    if topics:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"text": {"content": "🏷️ Topics"}}]}
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": ", ".join(topics)}}]}
        })
    
    # Metadata
    blocks.append({
        "object": "block",
        "type": "divider",
        "divider": {}
    })
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"text": {"content": "📄 Full Transcript"}}]}
    })
    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"text": {"content": f"Duration: {duration:.0f}s | Source: {file_name}"}}],
            "icon": {"emoji": "🎙️"}
        }
    })
    
    # Transcript (split into chunks if needed - Notion has 2000 char limit per block)
    if transcript:
        chunks = [transcript[i:i+1900] for i in range(0, len(transcript), 1900)]
        for chunk in chunks:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
            })
    
    return blocks

