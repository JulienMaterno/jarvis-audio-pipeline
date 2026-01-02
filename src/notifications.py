"""
Telegram notifications for the audio pipeline.
Sends processing reports similar to direct upload feedback.
"""

import os
import logging
import httpx
from typing import Dict, Any, Optional, List

logger = logging.getLogger('Jarvis.Notifications')

# Configuration
TELEGRAM_BOT_URL = os.getenv('TELEGRAM_BOT_URL', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')


async def send_telegram_message(text: str, chat_id: str = None) -> bool:
    """Send a message to Telegram."""
    if not TELEGRAM_BOT_URL:
        logger.warning("TELEGRAM_BOT_URL not configured, skipping notification")
        return False
    
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    if not target_chat_id:
        logger.warning("No chat_id and TELEGRAM_CHAT_ID not configured")
        return False
    
    url = f"{TELEGRAM_BOT_URL.rstrip('/')}/send_message"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json={
                "chat_id": int(target_chat_id),
                "text": text,
                "parse_mode": "Markdown"
            })
            
            if response.status_code == 200:
                logger.info(f"Telegram notification sent")
                return True
            else:
                logger.error(f"Telegram send failed: {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False


def send_telegram_message_sync(text: str, chat_id: str = None) -> bool:
    """Synchronous version of send_telegram_message."""
    if not TELEGRAM_BOT_URL:
        logger.warning("TELEGRAM_BOT_URL not configured")
        return False
    
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    if not target_chat_id:
        logger.warning("No chat_id configured")
        return False
    
    url = f"{TELEGRAM_BOT_URL.rstrip('/')}/send_message"
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json={
                "chat_id": int(target_chat_id),
                "text": text,
                "parse_mode": "Markdown"
            })
            
            if response.status_code == 200:
                logger.info(f"Telegram notification sent")
                return True
            else:
                logger.error(f"Telegram send failed: {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False


def build_processing_started_message(filename: str, file_size_mb: float = None, queue_position: int = None) -> str:
    """Build message when starting to process a file."""
    lines = ["🎙️ *Processing voice memo...*", ""]
    lines.append(f"📁 File: `{filename}`")
    
    if file_size_mb:
        lines.append(f"📊 Size: {file_size_mb:.1f} MB")
    
    if queue_position and queue_position > 1:
        lines.append(f"📋 Queue position: {queue_position}")
    
    lines.append("")
    lines.append("_This may take a few minutes..._")
    
    return "\n".join(lines)


def build_processing_complete_message(
    filename: str,
    analysis: Dict[str, Any],
    transcript_length: int = 0,
    processing_time_seconds: float = 0,
    source: str = "google_drive"
) -> str:
    """
    Build a comprehensive processing report message.
    Similar to direct upload feedback.
    """
    lines = []
    
    category = analysis.get('primary_category', 'recording')
    emoji_map = {
        "meeting": "📅",
        "journal": "📓",
        "reflection": "💭",
        "task_planning": "✅",
        "other": "📝"
    }
    emoji = emoji_map.get(category, "📝")
    
    # Header
    source_label = "Google Drive" if source == "google_drive" else "Upload"
    lines.append(f"{emoji} *Voice memo processed!*")
    lines.append(f"📁 `{filename}`")
    lines.append("")
    
    # What was created
    created_items = []
    
    # Journals
    journals = analysis.get('journals', [])
    journal_ids = analysis.get('journal_ids', [])
    if journal_ids or journals:
        for j in journals:
            date = j.get('date', 'today')
            mood = j.get('mood', j.get('overall_mood', ''))
            mood_str = f" (Mood: {mood})" if mood else ""
            created_items.append(f"📓 Journal for {date}{mood_str}")
            
            # Show tomorrow's focus if present
            tomorrow_focus = j.get('tomorrow_focus', [])
            if tomorrow_focus:
                created_items.append(f"   → {len(tomorrow_focus)} items for tomorrow")
    
    # Meetings
    meetings = analysis.get('meetings', [])
    meeting_ids = analysis.get('meeting_ids', [])
    if meeting_ids or meetings:
        for m in meetings:
            title = m.get('title', 'Untitled')
            person = m.get('person_name', '')
            if person:
                created_items.append(f"📅 Meeting: {title} with {person}")
            else:
                created_items.append(f"📅 Meeting: {title}")
    
    # Reflections
    reflections = analysis.get('reflections', [])
    reflection_ids = analysis.get('reflection_ids', [])
    if reflection_ids or reflections:
        for r in reflections:
            title = r.get('title', 'Untitled')
            topic_key = r.get('topic_key', '')
            if topic_key:
                created_items.append(f"💭 Reflection: {title}")
            else:
                created_items.append(f"💭 {title}")
    
    # Tasks
    tasks = analysis.get('tasks', [])
    task_ids = analysis.get('task_ids', [])
    task_count = len(task_ids) if task_ids else len(tasks)
    if task_count > 0:
        created_items.append(f"✅ {task_count} task(s) created")
    
    # Show created items
    if created_items:
        lines.append("*Created:*")
        for item in created_items:
            lines.append(f"  {item}")
        lines.append("")
    else:
        lines.append(f"_Recorded as: {category}_")
        lines.append("")
    
    # Contact linking feedback
    contact_matches = analysis.get('contact_matches', [])
    linked_contacts = [m for m in contact_matches if m.get('matched')]
    
    if linked_contacts:
        lines.append("*Contacts linked:*")
        for match in linked_contacts:
            linked = match.get('linked_contact', {})
            name = linked.get('name', match.get('searched_name', ''))
            company = linked.get('company', '')
            if company:
                lines.append(f"  👤 {name} ({company})")
            else:
                lines.append(f"  👤 {name}")
        lines.append("")
    
    # Stats footer
    stats = []
    if transcript_length > 0:
        words = transcript_length // 5  # Rough word count
        stats.append(f"~{words} words")
    if processing_time_seconds > 0:
        if processing_time_seconds < 60:
            stats.append(f"{processing_time_seconds:.0f}s")
        else:
            mins = processing_time_seconds / 60
            stats.append(f"{mins:.1f}min")
    
    if stats:
        lines.append(f"_({', '.join(stats)})_")
    
    return "\n".join(lines)


def build_processing_error_message(filename: str, error: str) -> str:
    """Build error message for failed processing."""
    lines = [
        "❌ *Processing failed*",
        "",
        f"📁 `{filename}`",
        "",
        f"Error: {error[:200]}"
    ]
    
    return "\n".join(lines)


def build_queue_status_message(
    queue_length: int,
    currently_processing: str = None,
    estimated_wait_minutes: int = None
) -> str:
    """Build queue status message."""
    lines = ["📋 *Processing Queue*", ""]
    
    if currently_processing:
        lines.append(f"▶️ Processing: `{currently_processing}`")
    
    if queue_length > 0:
        lines.append(f"📁 {queue_length} file(s) waiting")
        
        if estimated_wait_minutes:
            lines.append(f"⏱️ Est. wait: ~{estimated_wait_minutes} minutes")
    else:
        lines.append("✅ Queue is empty")
    
    return "\n".join(lines)
