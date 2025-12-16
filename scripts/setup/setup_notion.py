"""
Setup and test Notion API connection.
Discovers databases and pages, saves IDs to .env
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key
import logging
from notion_client import Client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('NotionSetup')

# Load environment
project_root = Path(__file__).parent
env_path = project_root / '.env'
load_dotenv(env_path)

def test_notion_connection():
    """Test Notion API connection and discover accessible resources."""
    
    api_key = os.getenv('NOTION_API_KEY')
    
    if not api_key:
        logger.error("❌ NOTION_API_KEY not found in .env file")
        return False
    
    logger.info("="*60)
    logger.info("Testing Notion API Connection")
    logger.info("="*60)
    logger.info(f"API Key prefix: {api_key[:20]}...")
    
    try:
        # Initialize client with new API version
        notion = Client(
            auth=api_key,
            notion_version="2025-09-03"
        )
        
        logger.info("\n🔍 Searching for accessible pages and databases...")
        
        # Search for data sources (in 2025-09-03, databases contain data sources)
        search_results = notion.search(
            filter={"value": "data_source", "property": "object"}
        )
        
        data_sources = search_results.get('results', [])
        
        logger.info(f"\n✓ Found {len(data_sources)} data source(s):")
        
        meeting_db_id = None
        meeting_data_source_id = None
        other_page_id = None
        
        for ds in data_sources:
            # In API version 2025-09-03, we get data_source objects
            ds_id = ds.get('id')
            
            # Get the parent database info
            parent = ds.get('parent', {})
            db_id = parent.get('database_id') if parent.get('type') == 'database_id' else None
            
            # Get title from properties
            properties = ds.get('properties', {})
            title_text = 'Untitled'
            
            # Try to extract a meaningful name
            if properties:
                # Look for Name or title property
                for prop_name, prop_data in properties.items():
                    if prop_data.get('type') == 'title':
                        title_text = prop_name
                        break
            
            # Better: use the database parent name if available
            # We'll need to fetch the database to get its title
            if db_id:
                try:
                    db_info = notion.databases.retrieve(database_id=db_id)
                    db_title = db_info.get('title', [])
                    if db_title:
                        title_text = db_title[0]['plain_text']
                except:
                    pass
            
            logger.info(f"\n  📊 {title_text}")
            logger.info(f"     Data Source ID: {ds_id}")
            logger.info(f"     Database ID: {db_id}")
            
            # Check if this is the Meeting Database
            if 'meeting' in title_text.lower():
                meeting_db_id = db_id
                meeting_data_source_id = ds_id
                logger.info(f"     ✓ This is the MEETING DATABASE")
        
        # Search for pages
        page_results = notion.search(
            filter={"value": "page", "property": "object"}
        )
        
        pages = page_results.get('results', [])
        
        logger.info(f"\n✓ Found {len(pages)} page(s):")
        
        for page in pages:
            page_id = page.get('id')
            title_prop = page.get('properties', {}).get('title', {})
            
            # Extract title text
            title_text = 'Untitled'
            if title_prop.get('type') == 'title' and title_prop.get('title'):
                title_text = title_prop['title'][0]['plain_text']
            
            logger.info(f"\n  📄 {title_text}")
            logger.info(f"     ID: {page_id}")
            
            # Check if this is the "Other" page
            if title_text.lower() == 'other':
                other_page_id = page_id
                logger.info(f"     ✓ This is the OTHER page")
        
        # Save discovered IDs to .env
        if meeting_data_source_id:
            set_key(env_path, 'NOTION_MEETING_DATA_SOURCE_ID', meeting_data_source_id)
            logger.info(f"\n✓ Saved NOTION_MEETING_DATA_SOURCE_ID to .env")
        else:
            logger.warning(f"\n⚠ Could not find 'Meeting Database' data source")
        
        if other_page_id:
            set_key(env_path, 'NOTION_OTHER_PAGE_ID', other_page_id)
            logger.info(f"✓ Saved NOTION_OTHER_PAGE_ID to .env")
        else:
            logger.warning(f"⚠ Could not find 'Other' page")
        
        logger.info("\n" + "="*60)
        logger.info("✅ Notion API connection successful!")
        logger.info("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error connecting to Notion: {e}")
        return False

def test_create_page():
    """Test creating a page in the Other section."""
    
    logger.info("\n" + "="*60)
    logger.info("Testing Page Creation")
    logger.info("="*60)
    
    api_key = os.getenv('NOTION_API_KEY')
    other_page_id = os.getenv('NOTION_OTHER_PAGE_ID')
    
    if not other_page_id:
        logger.error("❌ NOTION_OTHER_PAGE_ID not set. Run setup first.")
        return False
    
    notion = Client(
        auth=api_key,
        notion_version="2025-09-03"
    )
    
    try:
        # Create a test page
        logger.info(f"\n📝 Creating test page in 'Other'...")
        
        new_page = notion.pages.create(
            parent={"page_id": other_page_id},
            properties={
                "title": {
                    "title": [{"text": {"content": "🧪 Test Voice Memo"}}]
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "Summary"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "text": {"content": "This is a test page created by the audio-to-notion pipeline."}
                        }]
                    }
                },
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "Transcript"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "text": {"content": "Test transcript content goes here..."}
                        }]
                    }
                }
            ]
        )
        
        page_url = new_page.get('url')
        
        logger.info(f"\n✅ Test page created successfully!")
        logger.info(f"URL: {page_url}")
        logger.info(f"\nYou can delete this test page from Notion.")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Error creating page: {e}")
        return False

def main():
    """Run Notion setup and tests."""
    
    if not test_notion_connection():
        sys.exit(1)
    
    # Ask if user wants to test page creation
    logger.info("\n" + "="*60)
    response = input("\n📝 Test creating a page in 'Other'? (y/n): ").lower()
    
    if response == 'y':
        test_create_page()
    
    logger.info("\n✅ Notion setup complete!")
    logger.info("\nNext: Run full pipeline with: python main_dag.py --once")

if __name__ == '__main__':
    main()
