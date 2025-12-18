import os
import io
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger('Jarvis.GDrive')

# Need full drive scope to move files between folders
SCOPES = ['https://www.googleapis.com/auth/drive']

class GoogleDriveMonitor:
    """Monitor Google Drive folder for new audio files."""
    
    def __init__(self, credentials_file: str, folder_id: str):
        self.credentials_file = credentials_file
        self.folder_id = folder_id
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Drive API using service account."""
        # Check for service account JSON in environment (Cloud Run)
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        
        if service_account_json:
            # Load from environment variable (cloud deployment)
            try:
                service_account_info = json.loads(service_account_json)
                creds = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=SCOPES
                )
                logger.info("Loaded service account credentials from environment")
            except Exception as e:
                logger.error(f"Failed to load service account from environment: {e}")
                raise
        else:
            # Load from file (local development)
            credentials_path = Path(self.credentials_file).resolve()
            service_account_file = credentials_path.parent / 'service-account.json'
            
            if service_account_file.exists():
                creds = service_account.Credentials.from_service_account_file(
                    str(service_account_file),
                    scopes=SCOPES
                )
                logger.info("Loaded service account credentials from file")
            else:
                raise FileNotFoundError(
                    f"Service account file not found: {service_account_file}\n"
                    f"Please place your service account JSON at {service_account_file}"
                )
        
        self.service = build('drive', 'v3', credentials=creds)
        logger.info("Authenticated with Google Drive using service account")
    
    def list_audio_files(self, 
                        supported_formats: List[str],
                        modified_after: Optional[datetime] = None,
                        max_results: int = 100) -> List[Dict]:
        """List audio files in the monitored folder.
        
        Args:
            supported_formats: List of file extensions (e.g., ['.mp3', '.m4a'])
            modified_after: Only return files modified after this datetime
            max_results: Maximum number of files to return (default 100)
        
        Returns:
            List of file metadata dicts with keys: id, name, mimeType, modifiedTime, size
        """
        try:
            # Build query
            format_queries = [f"name contains '{ext[1:]}' or name contains '{ext[1:].upper()}'" 
                            for ext in supported_formats]
            format_query = ' or '.join(format_queries)
            
            query = f"'{self.folder_id}' in parents and ({format_query}) and trashed=false"
            
            if modified_after:
                timestamp = modified_after.isoformat() + 'Z'
                query += f" and modifiedTime > '{timestamp}'"
            
            # Execute query with pagination
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, mimeType, modifiedTime, size, parents)',
                orderBy='modifiedTime desc',
                pageSize=min(max_results, 100)  # Limit results to prevent long API calls
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Found {len(files)} audio files in Google Drive")
            return files
            
        except Exception as e:
            logger.error(f"Error listing files from Google Drive: {e}")
            return []
    
    def download_file(self, file_id: str, file_name: str, destination: Path) -> Optional[Path]:
        """Download a file from Google Drive.
        
        Args:
            file_id: Google Drive file ID
            file_name: Original filename
            destination: Directory to save the file
        
        Returns:
            Path to downloaded file, or None if failed
        """
        try:
            request = self.service.files().get_media(fileId=file_id)
            
            file_path = destination / file_name
            
            with io.FileIO(file_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.info(f"Download {int(status.progress() * 100)}%")
            
            logger.info(f"Downloaded: {file_name}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error downloading file {file_name}: {e}")
            return None
    
    def get_latest_unprocessed_file(self, 
                                   supported_formats: List[str],
                                   processed_ids: set,
                                   max_results: int = 50) -> Optional[Dict]:
        """Get the most recent file that hasn't been processed yet.
        
        Args:
            supported_formats: List of supported file extensions
            processed_ids: Set of file IDs that have already been processed
            max_results: Maximum files to check (default 50, prevents long scans)
        
        Returns:
            File metadata dict, or None if no unprocessed files
        """
        # Only fetch recent files to prevent long API calls
        files = self.list_audio_files(supported_formats, max_results=max_results)
        
        for file in files:
            if file['id'] not in processed_ids:
                return file
        
        return None
