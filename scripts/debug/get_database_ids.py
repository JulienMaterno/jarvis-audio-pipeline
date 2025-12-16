"""
Extract the correct database_id values from data_source objects
"""
import os
import sys
import json
from notion_client import Client

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config

def get_database_mappings():
    """Get the mapping from data_source_id to database_id"""
    client = Client(auth=Config.NOTION_API_KEY)
    
    print("\n" + "="*60)
    print("DATABASE ID MAPPINGS")
    print("="*60 + "\n")
    
    response = client.search(filter={"property": "object", "value": "data_source"})
    databases = response.get("results", [])
    
    mappings = {}
    
    for db in databases:
        title = db.get("title", [{}])[0].get("plain_text", "Untitled")
        data_source_id = db.get("id", "")
        
        # Get the database_id from the parent field
        parent = db.get("parent", {})
        database_id = parent.get("database_id")
        
        if database_id:
            mappings[title] = {
                "data_source_id": data_source_id,
                "database_id": database_id
            }
            
            print(f"{title}:")
            print(f"   Data Source ID (current): {data_source_id}")
            print(f"   Database ID (needed):     {database_id}")
            print()
    
    print("="*60)
    print("CONFIG.PY UPDATE NEEDED")
    print("="*60 + "\n")
    
    # Map to config names
    config_mapping = {
        "Meetings": ("NOTION_MEETING_DATABASE_ID", Config.NOTION_MEETING_DATABASE_ID),
        "Reflections/Ideas/Thoughts": ("NOTION_REFLECTIONS_DATABASE_ID", Config.NOTION_REFLECTIONS_DATABASE_ID),
        "Tasks": ("NOTION_TASKS_DATABASE_ID", Config.NOTION_TASKS_DATABASE_ID),
        "CRM": ("NOTION_CRM_DATABASE_ID", Config.NOTION_CRM_DATABASE_ID)
    }
    
    changes_needed = []
    
    for db_name, (config_name, current_value) in config_mapping.items():
        if db_name in mappings:
            correct_id = mappings[db_name]["database_id"]
            if current_value != correct_id:
                changes_needed.append(f"    {config_name} = '{correct_id}'  # Was: {current_value}")
    
    if changes_needed:
        print("Replace in config.py:\n")
        for change in changes_needed:
            print(change)
    else:
        print("✅ All IDs are correct!")
    
    print()

if __name__ == "__main__":
    get_database_mappings()
