#!/usr/bin/env python3
"""
Health check script for Jarvis deployment.
Run this to verify all systems are operational before going to production.
"""

import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def check_env_vars():
    """Check all required environment variables are set."""
    logger.info("Checking environment variables...")
    required_vars = [
        'GOOGLE_DRIVE_FOLDER_ID',
        'GOOGLE_DRIVE_PROCESSED_FOLDER_ID',
        'CLAUDE_API_KEY',
        'NOTION_API_KEY',
        'NOTION_MEETING_DATABASE_ID',
        'NOTION_CRM_DATABASE_ID',
        'NOTION_TASKS_DATABASE_ID',
        'NOTION_REFLECTIONS_DATABASE_ID',
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
            logger.error(f"  ✗ {var} not set")
        else:
            logger.info(f"  ✓ {var}")
    
    if missing:
        logger.error(f"\n{len(missing)} required environment variables missing!")
        return False
    
    logger.info("✓ All environment variables present\n")
    return True


def check_credentials():
    """Check Google Drive credentials files exist."""
    logger.info("Checking credential files...")
    
    creds_file = Path('data/credentials.json')
    token_file = Path('data/token.json')
    
    if not creds_file.exists():
        logger.error(f"  ✗ {creds_file} not found")
        logger.error("    Run: python scripts/setup/setup_gdrive.py")
        return False
    logger.info(f"  ✓ {creds_file}")
    
    if not token_file.exists():
        logger.warning(f"  ⚠ {token_file} not found (will be created on first run)")
    else:
        logger.info(f"  ✓ {token_file}")
    
    logger.info("✓ Credential files OK\n")
    return True


def check_google_drive():
    """Test Google Drive connection."""
    logger.info("Testing Google Drive connection...")
    try:
        from src.core.monitor import GoogleDriveMonitor
        from src.config import Config
        
        monitor = GoogleDriveMonitor(
            credentials_file=Config.GOOGLE_CREDENTIALS_FILE,
            folder_id=Config.GOOGLE_DRIVE_FOLDER_ID
        )
        
        files = monitor.list_audio_files(Config.SUPPORTED_FORMATS)
        logger.info(f"  ✓ Connected! Found {len(files)} audio files")
        logger.info("✓ Google Drive OK\n")
        return True
    except Exception as e:
        logger.error(f"  ✗ Google Drive error: {e}")
        return False


def check_claude_api():
    """Test Claude API connection."""
    logger.info("Testing Claude API...")
    try:
        import anthropic
        api_key = os.getenv('CLAUDE_API_KEY')
        
        client = anthropic.Anthropic(api_key=api_key)
        # Simple test request
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'OK'"}]
        )
        
        logger.info(f"  ✓ Connected! Response: {response.content[0].text}")
        logger.info("✓ Claude API OK\n")
        return True
    except Exception as e:
        logger.error(f"  ✗ Claude API error: {e}")
        return False


def check_notion_api():
    """Test Notion API connection."""
    logger.info("Testing Notion API...")
    try:
        from notion_client import Client
        
        api_key = os.getenv('NOTION_API_KEY')
        client = Client(auth=api_key, notion_version="2025-09-03")
        
        # Test each database
        databases = {
            'Meetings': os.getenv('NOTION_MEETING_DATABASE_ID'),
            'CRM': os.getenv('NOTION_CRM_DATABASE_ID'),
            'Tasks': os.getenv('NOTION_TASKS_DATABASE_ID'),
            'Reflections': os.getenv('NOTION_REFLECTIONS_DATABASE_ID'),
        }
        
        for name, db_id in databases.items():
            db = client.databases.retrieve(database_id=db_id)
            logger.info(f"  ✓ {name}: {db['title'][0]['plain_text']}")
        
        logger.info("✓ Notion API OK\n")
        return True
    except Exception as e:
        logger.error(f"  ✗ Notion API error: {e}")
        return False


def check_whisper_model():
    """Check Whisper model availability."""
    logger.info("Checking Whisper model...")
    try:
        from faster_whisper import WhisperModel
        
        model_name = os.getenv('WHISPER_MODEL', 'base')
        logger.info(f"  Testing model: {model_name}")
        
        # This will download if not cached
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        logger.info(f"  ✓ Model '{model_name}' loaded successfully")
        logger.info("✓ Whisper OK\n")
        return True
    except Exception as e:
        logger.error(f"  ✗ Whisper error: {e}")
        return False


def check_directories():
    """Ensure required directories exist."""
    logger.info("Checking directories...")
    
    dirs = ['temp', 'logs', 'data']
    for dir_name in dirs:
        path = Path(dir_name)
        path.mkdir(exist_ok=True)
        logger.info(f"  ✓ {dir_name}/")
    
    logger.info("✓ Directories OK\n")
    return True


def main():
    """Run all health checks."""
    logger.info("=" * 60)
    logger.info("JARVIS HEALTH CHECK")
    logger.info("=" * 60 + "\n")
    
    checks = [
        ("Environment Variables", check_env_vars),
        ("Credential Files", check_credentials),
        ("Directories", check_directories),
        ("Google Drive API", check_google_drive),
        ("Claude API", check_claude_api),
        ("Notion API", check_notion_api),
        ("Whisper Model", check_whisper_model),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            logger.error(f"\n✗ {name} check failed with exception: {e}\n")
            results[name] = False
    
    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {name}")
    
    logger.info(f"\n{passed}/{total} checks passed")
    
    if passed == total:
        logger.info("\n🎉 All systems operational! Ready for deployment.")
        return 0
    else:
        logger.error(f"\n⚠️  {total - passed} checks failed. Fix issues before deploying.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
