"""
Test creating a page in the Reflections database
"""
import os
import sys
from notion_client import Client
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config

def test_create_reflection():
    """Test creating a simple reflection entry"""
    client = Client(auth=Config.NOTION_API_KEY)
    
    print("\n" + "="*60)
    print("TEST: Creating Reflection Entry")
    print("="*60 + "\n")
    
    db_id = Config.NOTION_REFLECTIONS_DATABASE_ID
    print(f"Database ID: {db_id}\n")
    
    try:
        # Create a simple test page
        response = client.pages.create(
            parent={'database_id': db_id},
            properties={
                'Name': {
                    'title': [{'text': {'content': 'TEST - Reflection Entry'}}]
                },
                'Date': {
                    'date': {'start': datetime.now().isoformat()}
                }
            },
            children=[
                {
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': [{'text': {'content': 'This is a test reflection created by the access test script.'}}]
                    }
                }
            ]
        )
        
        page_id = response['id']
        page_url = response['url']
        
        print(f"✅ SUCCESS!")
        print(f"   Page ID: {page_id}")
        print(f"   URL: {page_url}")
        print(f"\n   The database IS accessible and pages can be created.")
        print(f"   You can delete this test page from Notion.")
        
    except Exception as e:
        print(f"❌ FAILED!")
        print(f"   Error: {e}")
        print(f"\n   This suggests a permissions or schema issue.")
    
    print()

if __name__ == "__main__":
    test_create_reflection()
