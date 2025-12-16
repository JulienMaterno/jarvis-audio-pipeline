"""
Google Drive Setup and Testing Helper Script

This script helps you:
1. Authenticate with Google Drive
2. List accessible folders
3. Test access to your voice memo folder
4. Verify audio files can be found

Usage:
    python setup_gdrive.py --test              # Test connection
    python setup_gdrive.py --list-folders      # List all folders
    python setup_gdrive.py --show-files        # Show files in configured folder
    python setup_gdrive.py --find-folder "Voice Memos"  # Find folder by name
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.core.monitor import GoogleDriveMonitor

logger = logging.getLogger('GDriveSetup')


def setup_simple_logging():
    """Setup simple console logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    return logging.getLogger('GDriveSetup')


class GoogleDriveSetup:
    """Helper class for Google Drive setup and testing."""
    
    def __init__(self):
        self.logger = setup_simple_logging()
        self.monitor = None
        
    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive.
        Returns True if successful, False otherwise.
        """
        try:
            self.logger.info("🔐 Authenticating with Google Drive...")
            self.logger.info("   (Browser will open for first-time authentication)")
            
            # Check if credentials file exists
            if not Path(Config.GOOGLE_CREDENTIALS_FILE).exists():
                self.logger.error(f"❌ Credentials file not found: {Config.GOOGLE_CREDENTIALS_FILE}")
                self.logger.error("   Please download credentials.json from Google Cloud Console")
                self.logger.error("   See GOOGLE_DRIVE_SETUP.md for instructions")
                return False
            
            # Create monitor (this will trigger authentication)
            self.monitor = GoogleDriveMonitor(
                credentials_file=Config.GOOGLE_CREDENTIALS_FILE,
                folder_id=Config.GOOGLE_DRIVE_FOLDER_ID or "root"  # Use root if no folder specified
            )
            
            self.logger.info("✓ Successfully authenticated with Google Drive")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Authentication failed: {e}")
            return False
    
    def list_all_folders(self) -> List[Dict]:
        """
        List all folders accessible in Google Drive.
        Returns list of folder metadata dicts.
        """
        if not self.monitor:
            if not self.authenticate():
                return []
        
        try:
            self.logger.info("\n📁 Listing all accessible folders...")
            
            # Query for folders
            query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
            
            results = self.monitor.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, parents, modifiedTime)',
                orderBy='name',
                pageSize=100
            ).execute()
            
            folders = results.get('files', [])
            
            if not folders:
                self.logger.info("   No folders found")
                return []
            
            self.logger.info(f"\n   Found {len(folders)} folders:\n")
            
            for folder in folders:
                folder_id = folder['id']
                folder_name = folder['name']
                self.logger.info(f"   📁 {folder_name}")
                self.logger.info(f"      ID: {folder_id}")
                self.logger.info("")
            
            return folders
            
        except Exception as e:
            self.logger.error(f"❌ Error listing folders: {e}")
            return []
    
    def find_folder_by_name(self, folder_name: str) -> Optional[Dict]:
        """
        Find a folder by name.
        Returns folder metadata dict or None if not found.
        """
        if not self.monitor:
            if not self.authenticate():
                return None
        
        try:
            self.logger.info(f"\n🔍 Searching for folder: '{folder_name}'...")
            
            query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
            
            results = self.monitor.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, parents, modifiedTime)',
                pageSize=10
            ).execute()
            
            folders = results.get('files', [])
            
            if not folders:
                self.logger.info(f"   ❌ Folder '{folder_name}' not found")
                return None
            
            if len(folders) > 1:
                self.logger.info(f"   ⚠️  Found {len(folders)} folders with this name:")
                for i, folder in enumerate(folders, 1):
                    self.logger.info(f"   {i}. {folder['name']} (ID: {folder['id']})")
                self.logger.info("\n   Using the first one. Specify folder ID in .env to choose a specific one.")
            
            folder = folders[0]
            self.logger.info(f"\n   ✓ Found folder: {folder['name']}")
            self.logger.info(f"     Folder ID: {folder['id']}")
            self.logger.info(f"\n   Add this to your .env file:")
            self.logger.info(f"   GOOGLE_DRIVE_FOLDER_ID={folder['id']}")
            
            return folder
            
        except Exception as e:
            self.logger.error(f"❌ Error searching for folder: {e}")
            return None
    
    def show_files_in_folder(self) -> List[Dict]:
        """
        Show all files in the configured folder.
        Returns list of file metadata dicts.
        """
        if not self.monitor:
            if not self.authenticate():
                return []
        
        if not Config.GOOGLE_DRIVE_FOLDER_ID:
            self.logger.error("❌ No folder ID configured in .env")
            self.logger.error("   Set GOOGLE_DRIVE_FOLDER_ID in your .env file")
            return []
        
        try:
            self.logger.info(f"\n📂 Checking folder: {Config.GOOGLE_DRIVE_FOLDER_ID}")
            
            # Get folder info
            folder_info = self.monitor.service.files().get(
                fileId=Config.GOOGLE_DRIVE_FOLDER_ID,
                fields='id,name'
            ).execute()
            
            self.logger.info(f"   Folder name: {folder_info['name']}")
            
            # List audio files
            audio_files = self.monitor.list_audio_files(
                supported_formats=Config.SUPPORTED_FORMATS
            )
            
            if not audio_files:
                self.logger.info("\n   ⚠️  No audio files found in this folder")
                self.logger.info("   Supported formats: " + ", ".join(Config.SUPPORTED_FORMATS))
                return []
            
            self.logger.info(f"\n   ✓ Found {len(audio_files)} audio file(s):\n")
            
            for file in audio_files:
                size_mb = int(file.get('size', 0)) / (1024 * 1024)
                self.logger.info(f"   🎵 {file['name']}")
                self.logger.info(f"      Size: {size_mb:.2f} MB")
                self.logger.info(f"      Modified: {file['modifiedTime']}")
                self.logger.info(f"      ID: {file['id']}")
                self.logger.info("")
            
            return audio_files
            
        except Exception as e:
            self.logger.error(f"❌ Error accessing folder: {e}")
            self.logger.error("   Check that the folder ID is correct and accessible")
            return []
    
    def test_connection(self) -> bool:
        """
        Test complete connection and file access.
        Returns True if everything works, False otherwise.
        """
        self.logger.info("=" * 70)
        self.logger.info("Google Drive Connection Test")
        self.logger.info("=" * 70)
        
        # Step 1: Authentication
        if not self.authenticate():
            return False
        
        # Step 2: Check configuration
        self.logger.info("\n📋 Configuration Check:")
        self.logger.info(f"   Credentials file: {Config.GOOGLE_CREDENTIALS_FILE}")
        self.logger.info(f"   Folder ID: {Config.GOOGLE_DRIVE_FOLDER_ID or 'Not set'}")
        
        if not Config.GOOGLE_DRIVE_FOLDER_ID:
            self.logger.error("\n❌ No folder ID configured!")
            self.logger.error("   Run: python setup_gdrive.py --list-folders")
            self.logger.error("   Then add GOOGLE_DRIVE_FOLDER_ID to .env")
            return False
        
        # Step 3: Check folder access
        files = self.show_files_in_folder()
        
        if files:
            self.logger.info("=" * 70)
            self.logger.info("✓ Connection test PASSED")
            self.logger.info("=" * 70)
            self.logger.info("\n✅ Everything is working! You can now run:")
            self.logger.info("   python main_dag.py --once")
            return True
        else:
            self.logger.info("=" * 70)
            self.logger.info("⚠️  Connection test PARTIAL")
            self.logger.info("=" * 70)
            self.logger.info("\n⚠️  Authentication works, but no audio files found")
            self.logger.info("   Upload some audio files to the folder and try again")
            return False


def main():
    """Main entry point for the setup script."""
    parser = argparse.ArgumentParser(
        description='Google Drive Setup and Testing Helper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup_gdrive.py --test
  python setup_gdrive.py --list-folders
  python setup_gdrive.py --show-files
  python setup_gdrive.py --find-folder "Voice Memos"
        """
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test complete Google Drive connection and file access'
    )
    
    parser.add_argument(
        '--list-folders',
        action='store_true',
        help='List all accessible folders in Google Drive'
    )
    
    parser.add_argument(
        '--show-files',
        action='store_true',
        help='Show audio files in configured folder'
    )
    
    parser.add_argument(
        '--find-folder',
        type=str,
        metavar='NAME',
        help='Find folder by name (e.g., "Voice Memos")'
    )
    
    args = parser.parse_args()
    
    # If no arguments, show help
    if not any([args.test, args.list_folders, args.show_files, args.find_folder]):
        parser.print_help()
        return
    
    try:
        # Validate config exists
        Config.validate()
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print("\nMake sure you have:")
        print("1. Created .env file (copy from .env.example)")
        print("2. Downloaded credentials.json from Google Cloud Console")
        print("\nSee GOOGLE_DRIVE_SETUP.md for detailed instructions")
        return
    
    setup = GoogleDriveSetup()
    
    try:
        if args.test:
            success = setup.test_connection()
            sys.exit(0 if success else 1)
        
        elif args.list_folders:
            setup.list_all_folders()
        
        elif args.show_files:
            setup.show_files_in_folder()
        
        elif args.find_folder:
            folder = setup.find_folder_by_name(args.find_folder)
            if not folder:
                sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
