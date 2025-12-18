#!/usr/bin/env python3
"""Check if Google Drive webhook is set up and active"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from google.oauth2 import service_account
from googleapiclient.discovery import build

def check_webhook():
    print("Checking Google Drive webhook status...\n")
    
    # Load service account
    service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
    if not service_account_json:
        service_account_file = Path(__file__).parent / 'data' / 'service-account.json'
        if not service_account_file.exists():
            print("❌ No service account credentials found")
            return
        
        creds = service_account.Credentials.from_service_account_file(
            str(service_account_file),
            scopes=['https://www.googleapis.com/auth/drive']
        )
    else:
        service_account_info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/drive']
        )
    
    service = build('drive', 'v3', credentials=creds)
    
    # Google Drive API doesn't have a direct way to list active watches
    # But we can check if the webhook endpoint exists in Cloud Run
    
    print("Note: Google Drive API doesn't provide a way to list active webhook subscriptions.")
    print("To verify the webhook is active, you need to:")
    print("1. Check Cloud Run logs for webhook calls")
    print("2. Upload a file to Google Drive and see if it triggers processing")
    print("\nTo set up the webhook, run:")
    print("  python setup_drive_webhook.py --url https://your-cloud-run-url/webhook/drive")
    print("\nWebhook expires after 7 days and needs to be renewed.")

if __name__ == "__main__":
    check_webhook()
