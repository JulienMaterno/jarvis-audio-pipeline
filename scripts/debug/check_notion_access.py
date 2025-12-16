"""
Check which Notion databases are accessible to the integration
"""
import os
import sys
from notion_client import Client

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

def check_database_access():
    """Check access to all configured databases"""
    client = Client(auth=Config.NOTION_API_KEY)
    
    print("\n" + "="*60)
    print("NOTION DATABASE ACCESS CHECK")
    print("="*60 + "\n")
    
    database_names = {
        'meetings': 'Meetings Database',
        'reflections': 'Reflections Database',
        'tasks': 'Tasks Database',
        'crm': 'CRM Database'
    }
    
    database_ids = {
        'meetings': Config.NOTION_MEETING_DATABASE_ID,
        'reflections': Config.NOTION_REFLECTIONS_DATABASE_ID,
        'tasks': Config.NOTION_TASKS_DATABASE_ID,
        'crm': Config.NOTION_CRM_DATABASE_ID
    }
    
    results = {}
    
    for db_key, db_name in database_names.items():
        db_id = database_ids.get(db_key)
        
        if not db_id:
            print(f"❌ {db_name}: NOT CONFIGURED")
            results[db_key] = False
            continue
        
        print(f"\nChecking {db_name}...")
        print(f"   ID: {db_id}")
        
        try:
            # Try to retrieve the database
            response = client.databases.retrieve(database_id=db_id)
            print(f"   ✅ ACCESSIBLE")
            print(f"   Title: {response.get('title', [{}])[0].get('plain_text', 'N/A')}")
            results[db_key] = True
            
        except Exception as e:
            print(f"   ❌ NOT ACCESSIBLE")
            print(f"   Error: {str(e)}")
            results[db_key] = False
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    accessible = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nAccessible: {accessible}/{total} databases")
    
    if accessible < total:
        print("\n⚠️  ACTION REQUIRED:")
        print("   For each inaccessible database:")
        print("   1. Open the database in Notion")
        print("   2. Click '...' menu (top right)")
        print("   3. Click 'Connections' or 'Add connections'")
        print("   4. Select your Jarvis integration")
    else:
        print("\n✅ All databases are accessible!")
    
    print()
    
    return all(results.values())

if __name__ == "__main__":
    success = check_database_access()
    sys.exit(0 if success else 1)
