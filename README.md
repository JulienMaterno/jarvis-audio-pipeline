# 🎤 Jarvis Audio Pipeline

> ⚠️ **LOCKED SERVICE** - This service is stable and production-ready. DO NOT modify without explicit user approval.

> **Audio ingestion only.** Monitors Google Drive for voice memos, transcribes using Modal (GPU), saves the transcript, then hands off to the Intelligence Service for analysis.

## 🎯 Role in the Ecosystem

This service does **ONE thing well**: audio → text. It does NOT contain any AI/LLM logic.

```
[Voice Memo] → Download → Transcribe (Modal GPU) → Save Transcript → Call Intelligence Service → Move to Processed
```

**Why no AI here?** All intelligence lives in `jarvis-intelligence-service`. This keeps the pipeline simple, focused, and maintainable.

---

## 🏗️ Architecture

### Pipeline Flow

```
┌─────────────────────┐
│  Google Drive       │  User drops voice memo
│  (Watched Folder)   │
└─────────┬───────────┘
          │ Webhook or Poll
          ▼
┌─────────────────────┐
│  Cloud Run Server   │  cloud_run_server.py (FastAPI)
│  /process/upload    │  Also handles direct uploads from Telegram
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  AudioPipeline      │  run_pipeline.py
│  (Orchestrator)     │  Coordinates all steps
└─────────┬───────────┘
          │
          ├── 1. download_task.py     → Download from Drive
          │
          ├── 2. transcribe_task.py   → Send to Modal (GPU)
          │                              ↓
          │                           [WhisperX on A10G GPU]
          │                              ↓
          │                           Return {text, segments, speakers}
          │
          ├── 3. analyze_task_multi.py → Save transcript to Supabase
          │                              → Call Intelligence Service
          │
          ├── 4. move_task.py          → Move to "Processed" folder
          │
          └── 5. cleanup_task.py       → Delete temp files
```

### Key Components

| File | Purpose |
|------|---------|
| `cloud_run_server.py` | FastAPI HTTP server (webhooks, direct uploads) |
| `run_pipeline.py` | `AudioPipeline` class - orchestrates all steps |
| `src/tasks/*.py` | Individual pipeline steps (download, transcribe, etc.) |
| `src/core/transcription_backends/` | Multi-backend transcription (Modal, External GPU, Local) |
| `src/supabase/multi_db.py` | Database operations (transcripts, pipeline_logs) |
| `modal_whisperx_v2.py` | Modal function definition (deployed separately) |

---

## 🔌 API Endpoints

### `GET /health`
Health check for Cloud Run.
```json
{"status": "healthy", "processing": false}
```

### `POST /process`
Process all available audio files in Google Drive.
```bash
# Called by Cloud Scheduler every 5 minutes
curl -X POST https://jarvis-audio-pipeline-xxx.run.app/process
```
**Parameters:**
- `background=true` - Return immediately, process async (for large files)
- `reset=true` - Clear processed files cache to force reprocessing

### `POST /process/upload`
**Primary endpoint for Telegram bot.** Process an uploaded audio file directly.
```bash
curl -X POST -F "file=@voice_memo.ogg" -F "username=bertan" \
  https://jarvis-audio-pipeline-xxx.run.app/process/upload
```
**Response:**
```json
{
  "status": "success",
  "category": "meeting",
  "summary": "📅 Meeting: Sales call with John\n✅ 3 task(s) created",
  "details": {
    "transcript_id": "uuid",
    "meeting_ids": ["uuid"],
    "task_ids": ["uuid", "uuid", "uuid"]
  }
}
```

### `POST /webhook/drive`
Google Drive push notification endpoint. Triggered automatically when files are added.

### `POST /renew-webhook`
Renew Google Drive webhook (24h expiry). Called by Cloud Scheduler daily.

### `GET /status`
Current processing status.
```json
{"status": "idle", "processing": false, "pipeline_ready": true}
```

---

## 📊 Database Schema

### `transcripts` (Supabase)
```sql
id              UUID PRIMARY KEY
source_file     TEXT           -- Original filename
full_text       TEXT           -- Complete transcript
audio_duration  FLOAT          -- Seconds
language        TEXT           -- e.g., "en"
segments        JSONB          -- [{start, end, text, speaker}]
speakers        TEXT[]         -- ["SPEAKER_00", "SPEAKER_01"]
created_at      TIMESTAMPTZ
```

### `pipeline_logs` (Supabase)
```sql
id              UUID PRIMARY KEY
run_id          UUID           -- Groups events in one pipeline run
event_type      TEXT           -- download, transcribe, analyze, complete, error
status          TEXT           -- started, success, error
message         TEXT
source_file     TEXT
duration_ms     INT
details         JSONB
created_at      TIMESTAMPTZ
```

---

## 🎙️ Transcription Backends

The pipeline supports **multiple transcription backends** with automatic fallback:

| Backend | When Used | Cost | Speed |
|---------|-----------|------|-------|
| **Modal** | Default (production) | ~$0.10-0.30/hour | Fast (A10G GPU) |
| **External GPU** | If `EXTERNAL_GPU_URL` set | Free | Fastest |
| **Local CPU** | Fallback | Free | Slow |

**Backend Selection Logic** (`src/core/transcription_backends/router.py`):
1. Check if `TRANSCRIPTION_BACKEND` env var forces a specific backend
2. Try External GPU if `EXTERNAL_GPU_URL` is set and reachable
3. Try Modal if authenticated
4. Fall back to local CPU

---

## 🚀 Deployment

### Automatic via GitHub (Recommended)
Push to `main` → Cloud Build → Cloud Run (automatic)

```bash
git push origin main
```

Cloud Build triggers:
- **Trigger**: `jarvis-audio-pipeline-deploy`
- **Branch**: `^main$`
- **Config**: `cloudbuild.yaml`

### Environment Variables (Cloud Run)
```
GOOGLE_DRIVE_FOLDER_ID        # Folder to watch
GOOGLE_DRIVE_PROCESSED_FOLDER_ID  # Where to move processed files
INTELLIGENCE_SERVICE_URL      # https://jarvis-intelligence-service-xxx.run.app
SUPABASE_URL                  # Database URL
SUPABASE_KEY                  # Database key
GOOGLE_TOKEN_JSON             # OAuth token (JSON string)
```

### Modal Setup (One-time)
```bash
# Deploy the Modal function
modal deploy modal_whisperx_v2.py
```

---

## 🔧 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run locally
python cloud_run_server.py

# Test health
curl http://localhost:8080/health
```

---

## 🔐 Error Handling

### Retry Logic
- Intelligence Service calls retry **3 times** with exponential backoff
- Modal transcription has built-in retries

### Pipeline Failures
- All events logged to `pipeline_logs` table
- Errors include full stack trace in `message` field
- Temp files cleaned up even on error

### Monitoring
```sql
-- Recent errors
SELECT * FROM pipeline_logs 
WHERE status = 'error' 
ORDER BY created_at DESC 
LIMIT 10;

-- Pipeline success rate
SELECT 
  date_trunc('day', created_at) as day,
  COUNT(*) FILTER (WHERE status = 'success') as success,
  COUNT(*) FILTER (WHERE status = 'error') as errors
FROM pipeline_logs 
WHERE event_type = 'pipeline_complete'
GROUP BY 1 ORDER BY 1 DESC;
```

---

## 📁 Project Structure

```
jarvis-audio-pipeline/
├── cloud_run_server.py    # FastAPI server (entry point)
├── run_pipeline.py        # AudioPipeline orchestrator
├── modal_whisperx_v2.py   # Modal function (deployed separately)
├── src/
│   ├── config.py          # Configuration (env vars)
│   ├── tasks/             # Pipeline steps
│   │   ├── download_task.py
│   │   ├── transcribe_task.py
│   │   ├── analyze_task_multi.py
│   │   ├── move_task.py
│   │   └── cleanup_task.py
│   ├── core/
│   │   ├── transcription_backends/  # Multi-backend support
│   │   └── monitor.py     # Google Drive monitoring
│   └── supabase/
│       └── multi_db.py    # Database operations
├── cloudbuild.yaml        # Cloud Build config
├── Dockerfile
└── requirements.txt
```

---

## ⚠️ Important Notes

### DO NOT
- ❌ Add AI/LLM logic here (goes in Intelligence Service)
- ❌ Manually deploy (`gcloud builds submit` will fail due to missing secrets)
- ❌ Modify transcription flow without testing Modal integration
- ❌ Store audio files permanently (ephemeral /tmp only)

### DO
- ✅ Push to main for automatic deployment
- ✅ Check `pipeline_logs` table for debugging
- ✅ Use `/process/upload` for Telegram bot integration
- ✅ Renew webhook daily via Cloud Scheduler
