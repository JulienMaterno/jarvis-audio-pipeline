"""
Analyze Task: Extract structured information from transcript using Claude AI.
"""

import logging
from typing import Dict, Any
import os
from anthropic import Anthropic

logger = logging.getLogger('Jarvis.Tasks.Analyze')

# Global analyzer instance
_anthropic_client = None


def get_anthropic_client() -> Anthropic:
    """Get or create global Anthropic client instance."""
    global _anthropic_client
    if _anthropic_client is None:
        api_key = os.getenv('CLAUDE_API_KEY')
        if not api_key:
            raise ValueError("CLAUDE_API_KEY not found in environment")
        _anthropic_client = Anthropic(api_key=api_key)
    return _anthropic_client


def analyze_transcript(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task: Analyze transcript and extract structured information using Claude AI.
    
    Input (from context):
        - transcript: Full transcript text (from transcribe task)
        - file_name: Original filename (from download task)
    
    Output (to context):
        - is_meeting: Boolean - True if this is a meeting/conversation summary
        - title: Generated conversation title
        - summary: Brief summary
        - people_mentioned: List of people with context
        - topics: List of topic tags
        - action_items: List of action items
        - key_points: List of key points
    """
    logger.info("Starting analysis task")
    
    transcribe_result = context['task_results'].get('transcribe_audio', {})
    download_result = context['task_results'].get('download_audio_file', {})
    
    transcript = transcribe_result.get('text')
    file_name = download_result.get('file_name', 'unknown.mp3')
    
    if not transcript:
        raise ValueError("No transcript found in context")
    
    logger.info(f"Analyzing transcript from: {file_name}")
    logger.info(f"Transcript length: {len(transcript)} characters")
    
    # Get Claude client
    client = get_anthropic_client()
    model = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
    
    # Analyze with Claude
    prompt = f"""Analyze this voice memo transcript and extract structured information.

Transcript:
{transcript}

Please provide your analysis in the following format:

**IS_MEETING**: [YES/NO] - Is this a meeting summary, conversation with others, or interview? (YES) Or is it a personal note, thought, or solo reflection? (NO)

**PERSON**: [The main person this meeting/conversation was with, or "None" if not applicable. Extract ONLY the person's name, e.g. "John Smith" not "John Smith from Company X"]

**LOCATION**: [Where this took place if mentioned, e.g. "Coffee shop", "Zoom call", "Office", or "None"]

**TITLE**: [A clear, descriptive title for this content]

**SUMMARY**: [2-3 sentences summarizing the main content]

**KEY POINTS**:
- [Point 1]
- [Point 2]
- [Point 3]

**ACTION ITEMS**:
- [Action 1 if any]
- [Action 2 if any]

**PEOPLE MENTIONED**:
- [Name 1]: [Context/relevance]
- [Name 2]: [Context/relevance]

**TOPICS/TAGS**: [comma-separated list of relevant topics for organization]

Be specific and extract real information from the transcript. If there are no action items or people mentioned, explicitly say "None"."""

    logger.info(f"Sending to Claude ({model})...")
    
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    analysis_text = response.content[0].text
    logger.info(f"Claude analysis received ({response.usage.input_tokens} in, {response.usage.output_tokens} out)")
    
    # Parse Claude's response
    is_meeting = "YES" in analysis_text.split("**IS_MEETING**:")[1].split("\n")[0].upper() if "**IS_MEETING**:" in analysis_text else False
    
    # Extract sections
    def extract_section(text, start_marker, end_marker=None):
        """Extract content between markers."""
        if start_marker not in text:
            return ""
        content = text.split(start_marker)[1]
        if end_marker and end_marker in content:
            content = content.split(end_marker)[0]
        return content.strip()
    
    person = extract_section(analysis_text, "**PERSON**:", "**LOCATION**") or "None"
    person = person if person.lower() != "none" else None
    
    location = extract_section(analysis_text, "**LOCATION**:", "**TITLE**") or "None"
    location = location if location.lower() != "none" else None
    
    title = extract_section(analysis_text, "**TITLE**:", "**SUMMARY**") or file_name
    summary = extract_section(analysis_text, "**SUMMARY**:", "**KEY POINTS**") or ""
    key_points_section = extract_section(analysis_text, "**KEY POINTS**:", "**ACTION ITEMS**") or ""
    action_items_section = extract_section(analysis_text, "**ACTION ITEMS**:", "**PEOPLE MENTIONED**") or ""
    people_section = extract_section(analysis_text, "**PEOPLE MENTIONED**:", "**TOPICS/TAGS**") or ""
    topics_section = extract_section(analysis_text, "**TOPICS/TAGS**:", None) or ""
    
    # Parse lists
    key_points = [line.strip('- ').strip() for line in key_points_section.split('\n') if line.strip().startswith('-')]
    action_items = [line.strip('- ').strip() for line in action_items_section.split('\n') if line.strip().startswith('-') and line.strip().lower() != '- none']
    people = [line.strip('- ').strip() for line in people_section.split('\n') if line.strip().startswith('-') and line.strip().lower() != '- none']
    topics = [t.strip() for t in topics_section.replace('\n', '').split(',') if t.strip()]
    
    logger.info(f"✓ Analysis complete: {'MEETING' if is_meeting else 'NOTE'}")
    logger.info(f"  Person: {person or 'N/A'}")
    logger.info(f"  Location: {location or 'N/A'}")
    logger.info(f"  Title: {title}")
    logger.info(f"  Topics: {', '.join(topics[:3])}")
    logger.info(f"  Action items: {len(action_items)}")
    
    return {
        'is_meeting': is_meeting,
        'person': person,
        'location': location,
        'title': title,
        'summary': summary,
        'key_points': key_points,
        'action_items': action_items,
        'people_mentioned': people,
        'topics': topics,
        'analysis_full_text': analysis_text
    }

