import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Central configuration for the audio processing pipeline."""
    
    # Get base directory (where config.py lives - src/)
    BASE_DIR = Path(__file__).parent.resolve()
    # Project root is one level up from src/
    PROJECT_ROOT = BASE_DIR.parent
    
    # =========================================================================
    # SUPABASE (Primary Data Store)
    # =========================================================================
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # =========================================================================
    # GOOGLE DRIVE
    # =========================================================================
    GOOGLE_CREDENTIALS_FILE = str(PROJECT_ROOT / 'data' / os.getenv('GOOGLE_DRIVE_CREDENTIALS_FILE', 'credentials.json'))
    GOOGLE_TOKEN_FILE = str(PROJECT_ROOT / 'data' / 'token.json')
    GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    GOOGLE_DRIVE_PROCESSED_FOLDER_ID = os.getenv('GOOGLE_DRIVE_PROCESSED_FOLDER_ID')
    
    # =========================================================================
    # CLAUDE API
    # =========================================================================
    ANTHROPIC_API_KEY = os.getenv('CLAUDE_API_KEY')
    CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-3-5-haiku-20241022')
    
    # =========================================================================
    # NOTION (Legacy - kept for jarvis-backend sync reference)
    # NOTE: This pipeline NO LONGER writes to Notion directly.
    # Notion sync is handled by jarvis-backend from Supabase.
    # =========================================================================
    NOTION_API_KEY = os.getenv('NOTION_API_KEY')  # May still be needed for CRM lookup
    NOTION_MEETING_DATABASE_ID = os.getenv('NOTION_MEETING_DATABASE_ID', '297cd3f1-eb28-810f-86f0-f142f7e3a5ca')
    NOTION_CRM_DATABASE_ID = os.getenv('NOTION_CRM_DATABASE_ID', '310acdfc-72d2-42ba-be6b-735ba6057e1c')
    NOTION_TASKS_DATABASE_ID = os.getenv('NOTION_TASKS_DATABASE_ID', '2b3cd3f1-eb28-8004-a33a-d26b8bb3fa58')
    NOTION_REFLECTIONS_DATABASE_ID = os.getenv('NOTION_REFLECTIONS_DATABASE_ID', '2b3cd3f1-eb28-80a8-8999-e731bdaf433e')
    NOTION_DATABASE_ID = NOTION_MEETING_DATABASE_ID  # Legacy
    
    # =========================================================================
    # PROCESSING SETTINGS
    # =========================================================================
    CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL_SECONDS', 120))
    WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')
    
    # Directories - cloud-friendly paths (use /tmp for ephemeral cloud storage)
    # Local: uses project root. Cloud: uses /tmp (ephemeral but works with Cloud Run)
    TEMP_AUDIO_DIR = Path(os.getenv('TEMP_AUDIO_DIR', str(PROJECT_ROOT / 'temp')))
    LOG_DIR = Path(os.getenv('LOG_DIR', str(PROJECT_ROOT / 'logs')))
    TRANSCRIPTS_DIR = Path(os.getenv('TRANSCRIPTS_FOLDER', str(PROJECT_ROOT / 'Transcripts')))
    
    # Supported audio formats
    SUPPORTED_FORMATS = ['.mp3', '.m4a', '.wav', '.ogg', '.flac']
    
    @classmethod
    def validate(cls):
        """Validate that all required config values are present."""
        required = [
            ('SUPABASE_URL', cls.SUPABASE_URL),
            ('SUPABASE_KEY', cls.SUPABASE_KEY),
            ('GOOGLE_DRIVE_FOLDER_ID', cls.GOOGLE_DRIVE_FOLDER_ID),
            ('ANTHROPIC_API_KEY', cls.ANTHROPIC_API_KEY),
        ]
        
        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")
        
        # Create directories if they don't exist
        cls.TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
