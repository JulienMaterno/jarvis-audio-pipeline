# Google Drive Helper Commands - Quick Reference

## 🚀 Quick Start

```powershell
# 1. Authenticate and list all folders
python setup_gdrive.py --list-folders

# 2. Find your voice memo folder
python setup_gdrive.py --find-folder "Voice Memos"

# 3. Copy the folder ID it shows and add to .env:
#    GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here

# 4. Test everything works
python setup_gdrive.py --test
```

---

## 📋 All Available Commands

### Test Connection
```powershell
python setup_gdrive.py --test
```
**What it does:**
- ✓ Authenticates with Google Drive
- ✓ Verifies credentials.json exists
- ✓ Checks folder ID is configured
- ✓ Lists audio files in folder
- ✓ Confirms everything is ready

**When to use:** After initial setup or to troubleshoot issues

---

### List All Folders
```powershell
python setup_gdrive.py --list-folders
```
**What it does:**
- Shows all folders accessible in your Google Drive
- Displays folder names and IDs
- Helps you find the right folder ID

**Output example:**
```
📁 Voice Memos
   ID: 1a2b3c4d5e6f7g8h9i0j

📁 Recordings
   ID: 9z8y7x6w5v4u3t2s1r0q
```

---

### Find Folder by Name
```powershell
python setup_gdrive.py --find-folder "Voice Memos"
```
**What it does:**
- Searches for folder with specific name
- Shows folder ID to add to .env
- Handles multiple folders with same name

**Output example:**
```
✓ Found folder: Voice Memos
  Folder ID: 1a2b3c4d5e6f7g8h9i0j

Add this to your .env file:
GOOGLE_DRIVE_FOLDER_ID=1a2b3c4d5e6f7g8h9i0j
```

---

### Show Files in Configured Folder
```powershell
python setup_gdrive.py --show-files
```
**What it does:**
- Lists all audio files in your configured folder
- Shows file sizes and modification dates
- Verifies folder access works

**Output example:**
```
📂 Checking folder: 1a2b3c4d5e6f7g8h9i0j
   Folder name: Voice Memos

✓ Found 3 audio file(s):

🎵 recording_001.m4a
   Size: 2.34 MB
   Modified: 2025-11-15T10:30:00.000Z
   ID: abc123def456

🎵 meeting_notes.mp3
   Size: 5.12 MB
   Modified: 2025-11-15T14:22:00.000Z
   ID: ghi789jkl012
```

---

## 🔧 Troubleshooting Commands

### Problem: "Credentials file not found"
```powershell
# Check if credentials.json exists
Test-Path credentials.json

# If false, download from Google Cloud Console
# See GOOGLE_DRIVE_SETUP.md Step 3
```

### Problem: "No folder ID configured"
```powershell
# Find your folder and get the ID
python setup_gdrive.py --find-folder "Your Folder Name"

# Or list all folders
python setup_gdrive.py --list-folders

# Then edit .env and add:
# GOOGLE_DRIVE_FOLDER_ID=the_folder_id_you_found
```

### Problem: "Authentication failed"
```powershell
# Delete old token and re-authenticate
Remove-Item token.json -ErrorAction SilentlyContinue
python setup_gdrive.py --test
```

### Problem: "No audio files found"
```powershell
# Check what's in the folder
python setup_gdrive.py --show-files

# Verify supported formats
# MP3, M4A, WAV, OGG, FLAC
```

---

## 📝 Workflow for First-Time Setup

### Step 1: Get credentials.json
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project and enable Drive API
3. Create OAuth credentials (Desktop app)
4. Download as `credentials.json`
5. Place in project folder

**Verify:**
```powershell
Test-Path credentials.json
# Should return: True
```

---

### Step 2: Find your folder
```powershell
# Option A: Search by name
python setup_gdrive.py --find-folder "Voice Memos"

# Option B: List all and pick one
python setup_gdrive.py --list-folders
```

**Copy the folder ID shown**

---

### Step 3: Configure .env
```powershell
# Open .env file
notepad .env

# Add the folder ID:
# GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here
```

---

### Step 4: Test everything
```powershell
python setup_gdrive.py --test
```

**Expected output:**
```
============================================================
Google Drive Connection Test
============================================================

🔐 Authenticating with Google Drive...
✓ Successfully authenticated with Google Drive

📋 Configuration Check:
   Credentials file: credentials.json
   Folder ID: 1a2b3c4d5e6f7g8h9i0j

📂 Checking folder: 1a2b3c4d5e6f7g8h9i0j
   Folder name: Voice Memos

✓ Found 3 audio file(s):
   [files listed]

============================================================
✓ Connection test PASSED
============================================================

✅ Everything is working! You can now run:
   python main_dag.py --once
```

---

## 🎯 Common Usage Patterns

### First-time setup
```powershell
python setup_gdrive.py --find-folder "Voice Memos"
# Copy folder ID to .env
python setup_gdrive.py --test
```

### Check if new files appeared
```powershell
python setup_gdrive.py --show-files
```

### Verify connection after changing settings
```powershell
python setup_gdrive.py --test
```

### Switch to different folder
```powershell
# Find the new folder
python setup_gdrive.py --list-folders

# Update .env with new folder ID
# Test connection
python setup_gdrive.py --test
```

---

## 📚 Related Documentation

- **[GOOGLE_DRIVE_SETUP.md](GOOGLE_DRIVE_SETUP.md)** - Complete setup guide with screenshots
- **[QUICKSTART.md](QUICKSTART.md)** - Full pipeline setup walkthrough
- **[README.md](README.md)** - Main project documentation

---

## 💡 Tips

### Tip 1: Shared folders
If your folder is "Shared with me":
1. Right-click folder in Drive
2. Select "Add shortcut to Drive"
3. Choose "My Drive"
4. Now you can access it with the script

### Tip 2: Multiple folders
To monitor multiple folders:
1. Create separate .env files (.env.voicememos, .env.recordings)
2. Switch between them when running
3. Or modify the code to accept folder ID as parameter

### Tip 3: Browser doesn't open
If browser doesn't open during auth:
1. Copy URL from terminal
2. Paste in browser
3. Complete authentication
4. May need to copy code back to terminal

---

**Need more help?** See [GOOGLE_DRIVE_SETUP.md](GOOGLE_DRIVE_SETUP.md) for detailed instructions.
