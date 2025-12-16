#!/usr/bin/env python3
"""
Setup Google Drive webhook (push notifications) for audio folder.

This script creates a 'watch' on your Google Drive folder so that Google
sends push notifications to your Cloud Run service when files are added.

Watches expire after ~24 hours, so you'll need to renew them periodically.
We'll set up a Cloud Scheduler job to auto-renew daily.

Usage:
    python setup_drive_webhook.py --url https://your-service.run.app/webhook/drive
"""

import os
import sys
import json
import uuid
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from src.config import Config

# Channel ID for this watch (use a consistent ID so we can renew)
CHANNEL_ID = "jarvis-audio-pipeline-webhook"


def setup_watch(webhook_url: str, folder_id: str = None):
    """
    Set up a Google Drive watch on the audio folder.
    
    Args:
        webhook_url: The webhook endpoint URL (e.g., https://your-service.run.app/webhook/drive)
        folder_id: Google Drive folder ID (defaults to GOOGLE_DRIVE_FOLDER_ID env var)
    """
    # Load credentials
    token_json = os.getenv('GOOGLE_TOKEN_JSON')
    if not token_json:
        print("❌ Error: GOOGLE_TOKEN_JSON environment variable not set")
        sys.exit(1)
    
    token_data = json.loads(token_json)
    creds = Credentials.from_authorized_user_info(token_data)
    
    # Refresh if needed
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    # Build Drive API client
    service = build('drive', 'v3', credentials=creds)
    
    # Get folder ID
    if not folder_id:
        folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    
    if not folder_id:
        print("❌ Error: GOOGLE_DRIVE_FOLDER_ID not set")
        sys.exit(1)
    
    print(f"Setting up webhook for folder: {folder_id}")
    print(f"Webhook URL: {webhook_url}")
    print(f"Channel ID: {CHANNEL_ID}")
    
    # Create watch request
    # Note: Watches expire after ~24 hours and need to be renewed
    body = {
        'id': CHANNEL_ID,
        'type': 'web_hook',
        'address': webhook_url,
        # Optional: Add an expiration time (max ~1 week, but 24h is safer)
        # 'expiration': int((datetime.utcnow() + timedelta(hours=24)).timestamp() * 1000)
    }
    
    try:
        # Stop existing watch if any
        try:
            print("\nChecking for existing watch...")
            service.channels().stop(body={'id': CHANNEL_ID, 'resourceId': 'placeholder'}).execute()
            print("✓ Stopped existing watch")
        except Exception as e:
            # It's OK if there's no existing watch
            if 'not found' not in str(e).lower():
                print(f"  (No existing watch or error stopping: {e})")
        
        # Create new watch
        print("\nCreating new watch...")
        response = service.files().watch(
            fileId=folder_id,
            body=body,
            supportsAllDrives=True
        ).execute()
        
        print("\n✅ Webhook successfully set up!")
        print(f"Resource ID: {response.get('resourceId')}")
        print(f"Expiration: {response.get('expiration', 'Not specified')}")
        
        # Calculate expiration time if provided
        if 'expiration' in response:
            exp_timestamp = int(response['expiration']) / 1000
            exp_datetime = datetime.fromtimestamp(exp_timestamp)
            hours_until = (exp_datetime - datetime.now()).total_seconds() / 3600
            print(f"Expires at: {exp_datetime} ({hours_until:.1f} hours from now)")
            print(f"\n⚠️  Remember to renew before expiration!")
        
        print(f"\nGoogle Drive will now send notifications to:")
        print(f"  {webhook_url}")
        print(f"\nWhen a file is added to folder {folder_id}")
        
        return response
        
    except Exception as e:
        print(f"\n❌ Error setting up webhook: {e}")
        print(f"\nMake sure:")
        print(f"  1. The webhook URL is publicly accessible")
        print(f"  2. Your Cloud Run service allows unauthenticated requests to /webhook/drive")
        print(f"  3. The Google Drive API is enabled")
        sys.exit(1)


def stop_watch():
    """Stop the current webhook watch."""
    token_json = os.getenv('GOOGLE_TOKEN_JSON')
    if not token_json:
        print("❌ Error: GOOGLE_TOKEN_JSON environment variable not set")
        sys.exit(1)
    
    token_data = json.loads(token_json)
    creds = Credentials.from_authorized_user_info(token_data)
    
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    service = build('drive', 'v3', credentials=creds)
    
    try:
        # Note: We need the resourceId to stop, which we don't have stored
        # This is a limitation - you might want to store this when creating the watch
        print(f"⚠️  Cannot stop watch without resourceId")
        print(f"Watches auto-expire after ~24 hours anyway")
        print(f"Or you can stop manually in Google Cloud Console:")
        print(f"https://console.cloud.google.com/apis/credentials")
        
    except Exception as e:
        print(f"❌ Error stopping watch: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup Google Drive webhook")
    parser.add_argument(
        '--url',
        required=True,
        help='Webhook URL (e.g., https://your-service.run.app/webhook/drive)'
    )
    parser.add_argument(
        '--folder',
        help='Google Drive folder ID (defaults to GOOGLE_DRIVE_FOLDER_ID env var)'
    )
    parser.add_argument(
        '--stop',
        action='store_true',
        help='Stop the current watch instead of creating one'
    )
    
    args = parser.parse_args()
    
    if args.stop:
        stop_watch()
    else:
        setup_watch(args.url, args.folder)
