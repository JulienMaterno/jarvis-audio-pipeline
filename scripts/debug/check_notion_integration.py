"""
Check which Notion integration is being used and list accessible databases
"""
import os
import sys
from notion_client import Client

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config

def check_integration():
    """Check the current integration and list all accessible databases"""
    client = Client(auth=Config.NOTION_API_KEY)
    
    print("\n" + "="*60)
    print("NOTION INTEGRATION CHECK")
    print("="*60 + "\n")
    
    # Try to search for all databases
    try:
        print("Searching for ALL accessible databases...\n")
        response = client.search(filter={"property": "object", "value": "data_source"})
        
        databases = response.get("results", [])
        
        if not databases:
            print("❌ No databases found!")
            print("\nThis means the integration has no access to any databases.")
            print("\nTo fix this:")
            print("1. Go to https://www.notion.so/my-integrations")
            print("2. Find your Jarvis integration")
            print("3. Copy the integration name")
            print("4. Open each database in Notion")
            print("5. Click '...' → 'Connections' → Add that integration")
        else:
            print(f"✅ Found {len(databases)} accessible database(s):\n")
            
            for db in databases:
                title = db.get("title", [{}])[0].get("plain_text", "Untitled")
                db_id = db.get("id", "").replace("-", "")
                
                # Format ID to match config format
                formatted_id = f"{db_id[:8]}-{db_id[8:12]}-{db_id[12:16]}-{db_id[16:20]}-{db_id[20:]}"
                
                print(f"   • {title}")
                print(f"     ID: {formatted_id}")
                print()
            
            print("\n" + "="*60)
            print("COMPARISON WITH CONFIG")
            print("="*60 + "\n")
            
            accessible_ids = [db.get("id", "") for db in databases]
            
            config_dbs = {
                "Meetings": Config.NOTION_MEETING_DATABASE_ID,
                "Reflections": Config.NOTION_REFLECTIONS_DATABASE_ID,
                "Tasks": Config.NOTION_TASKS_DATABASE_ID,
                "CRM": Config.NOTION_CRM_DATABASE_ID
            }
            
            for name, db_id in config_dbs.items():
                if db_id in accessible_ids:
                    print(f"   ✅ {name}: ACCESSIBLE")
                else:
                    print(f"   ❌ {name}: NOT ACCESSIBLE (ID: {db_id})")
        
        print()
        
    except Exception as e:
        print(f"❌ Error searching databases: {e}")
        print("\nCheck that your NOTION_API_KEY in .env is correct.")

if __name__ == "__main__":
    check_integration()
