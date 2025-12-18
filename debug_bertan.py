"""Debug script to check task creation in pipeline."""
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client
import os

client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

print('=== RECENT PIPELINE LOGS (save_complete) ===')
logs = client.table('pipeline_logs').select('*').eq('event_type', 'save_complete').order('created_at', desc=True).limit(10).execute()
for log in logs.data:
    print(f"{log.get('created_at')[:16]} | {log.get('source_file')}")
    print(f"  Message: {log.get('message')}")
    details = log.get('details', {})
    if details:
        print(f"  Tasks: {details.get('tasks', 0)}, Meetings: {details.get('meetings', 0)}, Reflections: {details.get('reflections', 0)}")
    print()

print('=== TASKS WITH NOTION IDs NOW ===')
tasks = client.table('tasks').select('title,notion_page_id,created_at').order('created_at', desc=True).limit(10).execute()
for t in tasks.data:
    synced = "✅" if t.get('notion_page_id') else "❌"
    print(f"{synced} {t.get('title')}")
