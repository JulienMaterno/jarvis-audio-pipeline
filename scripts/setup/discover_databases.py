"""
Discover Notion database structure - find Meeting DB and CRM DB.
"""

import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

notion = Client(
    auth=os.getenv('NOTION_API_KEY'),
    notion_version="2025-09-03"
)

# Search for data sources
results = notion.search(filter={'value': 'data_source', 'property': 'object'})

print("\n" + "="*60)
print("DISCOVERING DATABASES")
print("="*60)

for ds in results['results']:
    ds_id = ds.get('id')
    parent = ds.get('parent', {})
    db_id = parent.get('database_id')
    
    if db_id:
        # Get database info
        try:
            db_info = notion.databases.retrieve(database_id=db_id)
            db_title = db_info.get('title', [])
            title_text = db_title[0]['plain_text'] if db_title else 'Untitled'
            
            print(f"\n📊 {title_text}")
            print(f"   Data Source ID: {ds_id}")
            print(f"   Database ID: {db_id}")
            
            # Show properties (schema)
            properties = ds.get('properties', {})
            if properties:
                print(f"   Properties:")
                for prop_name, prop_data in properties.items():
                    prop_type = prop_data.get('type')
                    print(f"      - {prop_name} ({prop_type})", end="")
                    
                    # If it's a relation, show what it relates to
                    if prop_type == 'relation':
                        rel_db_id = prop_data.get('relation', {}).get('database_id')
                        rel_ds_id = prop_data.get('relation', {}).get('data_source_id')
                        if rel_db_id:
                            print(f" → relates to DB: {rel_db_id}")
                        else:
                            print()
                    else:
                        print()
        except Exception as e:
            print(f"Error: {e}")

print("\n" + "="*60)
