#!/usr/bin/env python
"""Test Google Drive connection and file checking - simulating Airflow workflow."""
import sys
import os
sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("Testing Workflow: Check for new files")
print("=" * 60)

from src.config import Config
print(f"\nConfig:")
print(f"  GOOGLE_CREDENTIALS_FILE: {Config.GOOGLE_CREDENTIALS_FILE}")
print(f"  GOOGLE_DRIVE_FOLDER_ID: {Config.GOOGLE_DRIVE_FOLDER_ID}")
print(f"  Credentials file exists: {os.path.exists(Config.GOOGLE_CREDENTIALS_FILE)}")

try:
    # Import just the monitor task directly (not from __init__ which imports all)
    print("\nImporting monitor_task directly...")
    from src.tasks.monitor_task import monitor_google_drive
    print("Import complete!")
    
    print("\n" + "-" * 60)
    print("Running monitor_google_drive task (same as Airflow)...")
    print("-" * 60)
    
    # Create context like Airflow does
    context = {
        'processed_file_ids': set(),
        'in_progress_file_ids': set(),
        'task_results': {}
    }
    
    print("Calling monitor_google_drive...")
    result = monitor_google_drive(context)
    
    print(f"\nResult:")
    print(f"  file_found: {result.get('file_found', False)}")
    if result.get('file_metadata'):
        meta = result['file_metadata']
        print(f"  file_name: {meta.get('name')}")
        print(f"  file_id: {meta.get('id')}")
        print(f"  file_size: {meta.get('size')}")
    else:
        print("  file_metadata: None")
        
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
