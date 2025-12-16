"""
Script to inspect all Notion database structures and properties.
Helps understand the schema before implementing multi-database integration.
"""

import os
from dotenv import load_dotenv
from notion_client import Client
import json

load_dotenv()

# Initialize Notion client
notion = Client(auth=os.getenv('NOTION_API_KEY'))

# Database IDs from .env
databases = {
    'Meeting Database': os.getenv('NOTION_MEETING_DATA_SOURCE_ID'),
    'CRM Database': os.getenv('NOTION_CRM_DATA_SOURCE_ID'),
    'Tasks Database': os.getenv('NOTION_TASKS_DATA_SOURCE_ID'),
    'Reflections Database': os.getenv('NOTION_REFLECTIONS_DATA_SOURCE_ID'),
}

def inspect_database(db_id, db_name):
    """Retrieve and display database schema."""
    try:
        print(f"\n{'='*80}")
        print(f"DATABASE: {db_name}")
        print(f"ID: {db_id}")
        print(f"{'='*80}")
        
        if not db_id:
            print("⚠️  Database ID not configured in .env")
            return
        
        # Retrieve database metadata
        db = notion.databases.retrieve(database_id=db_id)
        
        print(f"\nTitle: {db.get('title', [{}])[0].get('plain_text', 'Untitled')}")
        print(f"\nProperties:")
        print("-" * 80)
        
        properties = db.get('properties', {})
        
        for prop_name, prop_data in properties.items():
            prop_type = prop_data.get('type')
            print(f"\n📋 {prop_name}")
            print(f"   Type: {prop_type}")
            
            # Show additional details for specific types
            if prop_type == 'select':
                options = prop_data.get('select', {}).get('options', [])
                if options:
                    print(f"   Options: {', '.join([opt['name'] for opt in options])}")
            
            elif prop_type == 'multi_select':
                options = prop_data.get('multi_select', {}).get('options', [])
                if options:
                    print(f"   Options: {', '.join([opt['name'] for opt in options])}")
            
            elif prop_type == 'relation':
                db_id = prop_data.get('relation', {}).get('database_id')
                print(f"   Related Database ID: {db_id}")
            
            elif prop_type == 'formula':
                expression = prop_data.get('formula', {}).get('expression')
                print(f"   Formula: {expression}")
        
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"❌ Error retrieving {db_name}: {e}")

def main():
    print("\n" + "="*80)
    print("NOTION DATABASE STRUCTURE INSPECTION")
    print("="*80)
    
    for db_name, db_id in databases.items():
        inspect_database(db_id, db_name)
    
    print("\n\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    configured = [name for name, db_id in databases.items() if db_id]
    missing = [name for name, db_id in databases.items() if not db_id]
    
    print(f"\n✅ Configured databases ({len(configured)}):")
    for name in configured:
        print(f"   - {name}")
    
    if missing:
        print(f"\n⚠️  Missing database IDs in .env ({len(missing)}):")
        for name in missing:
            print(f"   - {name}")
            env_var = f"NOTION_{name.upper().replace(' ', '_').replace('/', '_')}"
            print(f"     Add to .env: {env_var}=<database_id>")

if __name__ == '__main__':
    main()
