"""Quick script to verify file was moved to Processed Audiofiles folder."""
from gdrive_monitor import GoogleDriveMonitor

gdrive = GoogleDriveMonitor('credentials.json', '18YRKFGyraupk8V0qGmYZiJZ5p1w5Dgh4')
files = gdrive.service.files().list(
    q=f"'18YRKFGyraupk8V0qGmYZiJZ5p1w5Dgh4' in parents and trashed=false",
    fields='files(name, createdTime)'
).execute()

print('\nFiles in Processed Audiofiles folder:')
print('=' * 50)
for f in files.get('files', []):
    print(f"  - {f['name']}")

if not files.get('files'):
    print("  (empty)")
