"""
Inspect the actual structure of the accessible databases
"""
import os
import sys
import json
from notion_client import Client

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config

def inspect_databases():
    """Get detailed info about accessible databases"""
    client = Client(auth=Config.NOTION_API_KEY)
    
    print("\n" + "="*60)
    print("DATABASE STRUCTURE INSPECTION")
    print("="*60 + "\n")
    
    response = client.search(filter={"property": "object", "value": "data_source"})
    databases = response.get("results", [])
    
    for db in databases:
        title = db.get("title", [{}])[0].get("plain_text", "Untitled")
        db_id = db.get("id", "")
        object_type = db.get("object", "unknown")
        
        print(f"\n{'='*60}")
        print(f"Database: {title}")
        print(f"{'='*60}")
        print(f"ID: {db_id}")
        print(f"Object Type: {object_type}")
        print(f"\nFull Response:")
        print(json.dumps(db, indent=2))
        print()

if __name__ == "__main__":
    inspect_databases()
