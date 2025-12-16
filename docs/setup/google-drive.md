# Google Drive API Setup Guide

This guide will help you set up Google Drive API access for the audio processing pipeline.

## Overview

You need to:
1. Create a Google Cloud Project
2. Enable Google Drive API
3. Create OAuth 2.0 credentials
4. Get your folder ID
5. Test the connection

---

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a project"** dropdown at the top
3. Click **"New Project"**
4. Enter project name: `Audio Processing Pipeline`
5. Click **"Create"**
6. Wait for project creation (takes ~30 seconds)

---

## Step 2: Enable Google Drive API

1. Make sure your new project is selected (check top dropdown)
2. Go to **APIs & Services** → **Library**
   - Direct link: https://console.cloud.google.com/apis/library
3. Search for **"Google Drive API"**
4. Click on **"Google Drive API"**
5. Click **"Enable"**
6. Wait for API to be enabled

---

## Step 3: Create OAuth 2.0 Credentials

### Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
   - Direct link: https://console.cloud.google.com/apis/credentials/consent
2. Select **"External"** (unless you have a Google Workspace)
3. Click **"Create"**
4. Fill in required fields:
   - **App name**: `Audio Processing Pipeline`
   - **User support email**: Your email
   - **Developer contact email**: Your email
5. Click **"Save and Continue"**
6. On **Scopes** page: Click **"Save and Continue"** (no need to add scopes)
7. On **Test users** page: Click **"Add Users"**
   - Add your Google email address
   - Click **"Add"**
8. Click **"Save and Continue"**
9. Review and click **"Back to Dashboard"**

### Create Credentials

1. Go to **APIs & Services** → **Credentials**
   - Direct link: https://console.cloud.google.com/apis/credentials
2. Click **"+ Create Credentials"** at the top
3. Select **"OAuth client ID"**
4. Choose **Application type**: **"Desktop app"**
5. **Name**: `Audio Pipeline Desktop Client`
6. Click **"Create"**
7. A dialog appears with your Client ID and Client Secret
8. Click **"Download JSON"**
9. Save the file as `credentials.json` in your project folder:
   ```
   c:\Users\aaron\My Drive\Transcription Project\audio-to-notion\credentials.json
   ```

---

## Step 4: Get Your Google Drive Folder ID

### Option A: From Browser URL

1. Open [Google Drive](https://drive.google.com) in your browser
2. Navigate to the folder containing your voice memos
3. Click on the folder to open it
4. Look at the URL in your browser:
   ```
   https://drive.google.com/drive/folders/1a2b3c4d5e6f7g8h9i0j
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^
                                          This is your Folder ID
   ```
5. Copy the folder ID (the part after `folders/`)

### Option B: Using Our Helper Script

Run the folder finder script (we'll create this):
```powershell
python setup_gdrive.py --list-folders
```

---

## Step 5: Configure .env File

1. Open `.env` file in the project folder
2. Update these lines:
   ```bash
   GOOGLE_DRIVE_CREDENTIALS_FILE=credentials.json
   GOOGLE_DRIVE_FOLDER_ID=YOUR_FOLDER_ID_HERE
   ```
3. Replace `YOUR_FOLDER_ID_HERE` with your actual folder ID from Step 4

Example:
```bash
GOOGLE_DRIVE_FOLDER_ID=1a2b3c4d5e6f7g8h9i0j
```

---

## Step 6: First-Time Authentication

When you first run the pipeline, it will:
1. Open your default web browser
2. Ask you to sign in to your Google account
3. Show a warning: **"Google hasn't verified this app"**
   - Click **"Advanced"**
   - Click **"Go to Audio Processing Pipeline (unsafe)"**
4. Click **"Allow"** to grant access
5. The browser will show: **"The authentication flow has completed"**
6. Close the browser tab

A `token.json` file will be created automatically for future runs.

---

## Step 7: Test the Connection

Run the test script:
```powershell
python setup_gdrive.py --test
```

This will:
- Authenticate with Google Drive
- List files in your configured folder
- Verify API access is working

Expected output:
```
✓ Authenticated with Google Drive
✓ Found folder: Voice Memos
✓ Found 5 audio files:
  - recording_001.m4a (2.3 MB)
  - meeting_notes.mp3 (5.1 MB)
  ...
```

---

## Troubleshooting

### Error: "Access blocked: This app's request is invalid"

**Solution**: Make sure you completed the OAuth consent screen setup in Step 3.

### Error: "The caller does not have permission"

**Solution**: 
1. Make sure the Google Drive API is enabled
2. Check that you're using the correct Google account
3. Re-download credentials.json

### Error: "Folder not found" or "Empty folder"

**Solution**:
1. Verify the folder ID is correct
2. Make sure the folder is in "My Drive" (not "Shared with me")
3. If folder is shared, add it to "My Drive" first:
   - Right-click folder → "Add shortcut to Drive" → "My Drive"

### Error: "Invalid credentials file"

**Solution**:
1. Make sure `credentials.json` is in the project root folder
2. Re-download from Google Cloud Console if corrupted
3. Check file permissions (should be readable)

### Browser doesn't open during authentication

**Solution**:
1. Copy the URL from the terminal
2. Paste it in your browser manually
3. Complete authentication
4. Copy the authorization code back to the terminal

---

## Security Notes

### Files to NEVER commit to Git:
- `credentials.json` - Your OAuth credentials
- `token.json` - Your access token
- `.env` - Your configuration with folder IDs

These are already in `.gitignore`.

### Permissions Granted:
- **Read-only access** to your Google Drive files
- The app can only **view and download** files
- Cannot modify, delete, or upload files

### Revoking Access:
If you want to revoke access later:
1. Go to [Google Account Security](https://myaccount.google.com/permissions)
2. Find "Audio Processing Pipeline"
3. Click "Remove Access"

---

## Quick Reference

### Folder Structure
```
audio-to-notion/
├── credentials.json     ← Download from Google Cloud Console
├── token.json          ← Auto-generated after first auth
├── .env                ← Add your folder ID here
└── setup_gdrive.py     ← Helper script for testing
```

### Commands
```powershell
# List all accessible folders
python setup_gdrive.py --list-folders

# Test connection to specific folder
python setup_gdrive.py --test

# Show folder contents
python setup_gdrive.py --show-files
```

---

## Next Steps

After completing this setup:

1. ✅ Run `python setup_gdrive.py --test` to verify everything works
2. ✅ Upload a test audio file to your folder
3. ✅ Run `python main_dag.py --once` to process it
4. ✅ Check your Notion database for the result

---

**Need help?** Check the logs in `logs/` folder for detailed error messages.
