#!/usr/bin/env python
"""Test Google Drive connection in Docker container."""
import sys
import os
sys.path.insert(0, '/opt/jarvis')
os.chdir('/opt/jarvis')

from gdrive_monitor import GoogleDriveMonitor

try:
    print("Testing Google Drive connection...")
    print(f"Working directory: {os.getcwd()}")
    print(f"Credentials exist: {os.path.exists('credentials.json')}")
    gdrive = GoogleDriveMonitor('credentials.json', '1cTsGDNwVhmgcLx7JZtvrei8EFUQ7lwPc')
    files = gdrive.list_audio_files(['.mp3', '.m4a', '.wav', '.ogg'])
    print(f"Success! Found {len(files)} audio files")
    for f in files:
        print(f"  - {f['name']}")
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()
