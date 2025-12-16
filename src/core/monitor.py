import os
import io
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
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
        """Authenticate with Google Drive API using Secret Manager (cloud) or files (local)."""
        creds = None
        
        # Check if running in cloud with secrets (Secret Manager)
        token_json = os.getenv('GOOGLE_TOKEN_JSON')
        if token_json:
            try:
                creds = Credentials.from_authorized_user_info(
                    json.loads(token_json),
                    SCOPES
                )
                logger.info("Loaded credentials from Secret Manager")
            except Exception as e:
                logger.warning(f"Failed to load credentials from secret: {e}")
        
        # Fallback to file-based credentials (local development)
        if not creds:
            # Get absolute path for credentials file
            credentials_path = Path(self.credentials_file).resolve()
            token_file = credentials_path.parent / 'token.json'
            
            # Load existing credentials
            if token_file.exists():
                creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
                logger.info("Loaded credentials from token.json")
        
        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Refreshed expired Google Drive token")
                except Exception as e:
                    logger.warning(f"Token refresh failed: {e}. Need to re-authenticate.")
                    # Token refresh failed, need manual re-auth
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(credentials_path), SCOPES)
                    creds = flow.run_local_server(port=0)
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('drive', 'v3', credentials=creds)
        logger.info("Authenticated with Google Drive")
    
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
                fields='files(id, name, mimeType, modifiedTime, size)',
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
