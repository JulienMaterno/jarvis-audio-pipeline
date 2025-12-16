# Quick Start Guide - DAG Version

Get started with the DAG-based audio processing pipeline in 5 minutes.

## Prerequisites Checklist

- [ ] Python 3.9+ installed
- [ ] FFmpeg installed
- [ ] Google Drive folder created
- [ ] Notion database created

---

## Step 1: Install FFmpeg

**Windows (PowerShell):**
```powershell
choco install ffmpeg
```

**Verify installation:**
```powershell
ffmpeg -version
```

---

## Step 2: Set Up Python Environment

```powershell
# Navigate to project
cd "c:\Users\aaron\My Drive\Transcription Project\audio-to-notion"

# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

---

## Step 3: Configure API Keys

### Create .env file
```powershell
Copy-Item .env.example .env
notepad .env
```

### Fill in your credentials

```bash
# Google Drive
GOOGLE_DRIVE_CREDENTIALS_FILE=credentials.json
GOOGLE_DRIVE_FOLDER_ID=your_actual_folder_id_here

# Claude AI
ANTHROPIC_API_KEY=sk-ant-your_actual_key_here

# Notion
NOTION_API_KEY=secret_your_integration_token_here
NOTION_DATABASE_ID=your_database_id_here

# Settings (keep defaults)
CHECK_INTERVAL_SECONDS=120
WHISPER_MODEL=base
```

---

## Step 4: Get Your API Credentials

### Google Drive API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project → Enable Google Drive API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download as `credentials.json` → Place in project folder
5. Get folder ID from Drive URL: `drive.google.com/drive/folders/FOLDER_ID_HERE`

### Claude API

1. Sign up at [Anthropic Console](https://console.anthropic.com/)
2. Create API key → Copy it (starts with `sk-ant-`)

### Notion API

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create new integration → Copy token
3. Create database with properties:
   - Title (Title)
   - Summary (Text)
   - Attendees (Text)
   - Date (Date)
   - Duration (min) (Number)
   - Topics (Multi-select)
   - Audio Source (Select)
   - Status (Select)
4. **Share database with integration** (click Share button)
5. Copy database ID from URL: `notion.so/DATABASE_ID?v=...`

---

## Step 5: Test the Pipeline

### View Pipeline Structure
```powershell
python main_dag.py --summary
```

Should show:
```
DAG: audio_to_notion_pipeline
Description: Complete pipeline: Google Drive → Whisper → Claude → Notion
============================================================

· Monitor Google Drive
  |
· Download Audio
  |
· Transcribe with Whisper
  |
· Analyze with Claude
  |
· Save to Notion
  |
· Cleanup Files
```

### Generate Visualizations
```powershell
python visualize_pipeline.py
```

Opens `visualizations/pipeline_structure.html` in browser.

---

## Step 6: Run Your First Audio File

### Upload test audio to Google Drive
1. Put an audio file (MP3, M4A, etc.) in your configured folder
2. Wait a moment for sync

### Process it with visualization
```powershell
python main_dag.py --once --visualize
```

Watch the output:
```
[1/6] Monitor Google Drive...
[2/6] Download Audio...
[3/6] Transcribe with Whisper...
[4/6] Analyze with Claude...
[5/6] Save to Notion...
[6/6] Cleanup Files...

✓ Success! Notion page created: abc123
```

### Check results
- Open `visualizations/dag_execution.html` to see execution flow
- Check Notion database for new entry
- View logs in `logs/` folder

---

## Step 7: Run Continuously

```powershell
python main_dag.py
```

This will:
- Check for new files every 2 minutes
- Process them automatically
- Generate visualizations (add `--visualize` flag)
- Run until Ctrl+C

---

## Troubleshooting

### Authentication Issues

**Google Drive:**
```powershell
# Delete token and re-authenticate
Remove-Item token.json
python main_dag.py --once
```

**Notion:**
- Verify database is shared with integration
- Check property names match exactly (case-sensitive)

### Memory Issues

Edit `.env`:
```bash
WHISPER_MODEL=tiny  # Use smaller model
```

### Import Errors

```powershell
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### View Logs

```powershell
# View today's log
Get-Content .\logs\audio_pipeline_*.log -Wait
```

---

## Common Commands

```powershell
# Process one file with viz
python main_dag.py --once --visualize

# Run continuously
python main_dag.py

# Show structure only
python main_dag.py --summary

# Generate diagrams
python visualize_pipeline.py

# View logs
Get-Content .\logs\*.log -Tail 50
```

---

## File Locations

After setup, you should have:

```
audio-to-notion/
├── credentials.json    ← Google Drive credentials
├── token.json         ← Auto-generated after first run
├── .env               ← Your API keys (do not commit!)
├── venv/              ← Python virtual environment
├── temp/              ← Temporary downloads (auto-cleaned)
├── logs/              ← Application logs
└── visualizations/    ← Generated diagrams
```

---

## What's Next?

1. **Customize settings** in `.env` (check interval, model size)
2. **Read DAG_ARCHITECTURE.md** for architecture details
3. **Create custom tasks** in `tasks/` folder
4. **Add parallel processing** for speed improvements
5. **Set up monitoring** and alerts

---

## Need Help?

- Check `logs/` for error details
- Review `DAG_ARCHITECTURE.md` for architecture
- Test individual components (see Advanced Usage in README)
- Verify all API credentials are correct

---

**You're all set! 🎉**

Upload audio files to Google Drive and watch them automatically transcribed and saved to Notion.
