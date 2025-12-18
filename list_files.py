#!/usr/bin/env python3
"""List files in the Voice Memos folder."""
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import json

# Load token
with open('data/token.json') as f:
    token_data = json.load(f)
    
creds = Credentials.from_authorized_user_info(token_data)
service = build('drive', 'v3', credentials=creds)

# List files in folder
folder_id = '1cTsGDNwVhmgcLx7JZtvrei8EFUQ7lwPc'
results = service.files().list(
    q=f"'{folder_id}' in parents",
    orderBy='modifiedTime desc',
    pageSize=10,
    fields='files(id, name, mimeType, modifiedTime)'
).execute()

print('=== Files in Voice Memos folder ===')
for f in results.get('files', []):
    print(f"{f['name']} ({f['modifiedTime']})")
