"""
Check the actual permissions the integration has on each database
"""
import os
import sys
from notion_client import Client

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config

def check_database_permissions():
    """Check what we can actually do with each database"""
    client = Client(auth=Config.NOTION_API_KEY)
    
    print("\n" + "="*60)
    print("DATABASE PERMISSIONS CHECK")
    print("="*60 + "\n")
    
    databases = {
        "Meetings": Config.NOTION_MEETING_DATABASE_ID,
        "Reflections": Config.NOTION_REFLECTIONS_DATABASE_ID,
        "Tasks": Config.NOTION_TASKS_DATABASE_ID,
        "CRM": Config.NOTION_CRM_DATABASE_ID
    }
    
    for name, db_id in databases.items():
        print(f"\n{name} Database:")
        print(f"   ID: {db_id}")
        
        # Test 1: Can we retrieve the database?
        try:
            db = client.databases.retrieve(database_id=db_id)
            print(f"   ✅ Retrieve: SUCCESS")
            
            # Check if it has properties
            props = db.get('properties', {})
            print(f"   📋 Properties: {list(props.keys())}")
            
        except Exception as e:
            print(f"   ❌ Retrieve: FAILED - {e}")
            continue
        
        # Test 2: Can we query the database?
        try:
            results = client.databases.query(database_id=db_id, page_size=1)
            page_count = len(results.get('results', []))
            print(f"   ✅ Query: SUCCESS ({page_count} page(s) returned)")
        except Exception as e:
            print(f"   ❌ Query: FAILED - {e}")
        
        # Test 3: Can we create a page?
        try:
            # Try to create with minimal properties
            title_prop = None
            for prop_name, prop_data in props.items():
                if prop_data.get('type') == 'title':
                    title_prop = prop_name
                    break
            
            if title_prop:
                response = client.pages.create(
                    parent={'database_id': db_id},
                    properties={
                        title_prop: {
                            'title': [{'text': {'content': '[TEST] Permission Check'}}]
                        }
                    }
                )
                print(f"   ✅ Create: SUCCESS (page created)")
                
                # Clean up - delete the test page
                try:
                    client.pages.update(page_id=response['id'], archived=True)
                    print(f"   🗑️  Test page archived")
                except:
                    pass
            else:
                print(f"   ⚠️  Create: SKIPPED (no title property found)")
                
        except Exception as e:
            print(f"   ❌ Create: FAILED - {str(e)[:100]}")
    
    print("\n" + "="*60)
    print("DIAGNOSIS")
    print("="*60)
    print("""
If you see "Retrieve: SUCCESS" but "Create: FAILED", it means:
   • The database is shared with the integration (read access)
   • But the integration doesn't have WRITE permissions
   
TO FIX:
   1. Open each database in Notion
   2. Click the '...' menu (top right)  
   3. Click 'Connections'
   4. REMOVE the existing connection to your integration
   5. ADD it again - this should grant full permissions
   
OR create a NEW integration with full permissions:
   1. Go to https://www.notion.so/my-integrations
   2. Create a new integration
   3. Make sure it has "Insert content", "Update content", "Read content"
   4. Copy the new API key to your .env file
   5. Share all 4 databases with the NEW integration
""")
    print()

if __name__ == "__main__":
    check_database_permissions()
