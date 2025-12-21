# 🤖 Audio Pipeline - LLM Integration Guide

> **For AI Agents / Coding Assistants**: This document explains how to interact with the Audio Pipeline programmatically.

## ⚠️ CRITICAL: This Service Has NO AI Logic

**DO NOT** add AI/LLM calls here. This service:
1. Downloads audio files
2. Transcribes them (GPU via Modal)
3. Calls `jarvis-intelligence-service` for analysis

All "thinking" happens in the Intelligence Service.

---

## 🔌 Primary Integration Point

### For Telegram Bot: `/process/upload`

This is how the Telegram Bot sends voice memos for processing:

```python
import httpx

async def process_voice_memo(audio_file: bytes, filename: str, username: str):
    """Send a voice memo to the audio pipeline."""
    
    url = "https://jarvis-audio-pipeline-qkz4et4n4q-as.a.run.app/process/upload"
    
    files = {"file": (filename, audio_file, "audio/ogg")}
    data = {"username": username}
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(url, files=files, data=data)
        return response.json()
```

**Response Format:**
```json
{
  "status": "success",
  "category": "meeting",
  "summary": "📅 Meeting: Sales call with John\n✅ 3 task(s) created",
  "details": {
    "transcript_id": "550e8400-e29b-41d4-a716-446655440000",
    "transcript_length": 1523,
    "meetings_created": 1,
    "reflections_created": 0,
    "tasks_created": 3,
    "meeting_ids": ["..."],
    "task_ids": ["...", "...", "..."],
    "contact_matches": [
      {
        "searched_name": "John Smith",
        "matched": true,
        "linked_contact": {"name": "John Smith", "company": "Acme Corp"}
      }
    ]
  }
}
```

---

## 📊 Database Tables

### `transcripts`
Raw transcription data. Created by this pipeline before calling Intelligence Service.

```sql
-- Schema
id              UUID PRIMARY KEY
source_file     TEXT           -- Original filename (e.g., "voice_20240115.ogg")
full_text       TEXT           -- Complete transcript
audio_duration  FLOAT          -- Duration in seconds
language        TEXT           -- Detected language (e.g., "en", "tr")
segments        JSONB          -- Speaker-diarized segments
speakers        TEXT[]         -- List of identified speakers
model_used      TEXT           -- e.g., "whisper-large-v3"
created_at      TIMESTAMPTZ
```

### `pipeline_logs`
For debugging and monitoring pipeline health.

```sql
-- Schema
id              UUID PRIMARY KEY
run_id          UUID           -- Groups events from one processing run
event_type      TEXT           -- download, transcribe, analyze, pipeline_complete, pipeline_error
status          TEXT           -- started, success, error
message         TEXT           -- Human-readable status
source_file     TEXT           -- Which file was being processed
duration_ms     INT            -- How long the step took
details         JSONB          -- Extra context (transcript_id, meeting_ids, etc.)
created_at      TIMESTAMPTZ
```

---

## 🔄 Data Flow

```
1. Voice Memo arrives (Google Drive webhook OR direct upload)
                 │
                 ▼
2. AudioPipeline.process_file() or process_file_direct()
                 │
                 ├── download_task.py (if from Drive)
                 │
                 ├── transcribe_task.py
                 │       │
                 │       └── Modal GPU (WhisperX) → Returns {text, segments, speakers}
                 │
                 ├── analyze_task_multi.py
                 │       │
                 │       ├── Save transcript to Supabase (transcripts table)
                 │       │
                 │       └── POST /api/v1/process/{transcript_id} 
                 │               → Intelligence Service (THE BRAIN)
                 │               → Returns analysis + created records
                 │
                 ├── move_task.py (move to Processed folder)
                 │
                 └── cleanup_task.py (delete temp files)
```

---

## 🔐 Error Handling

### Intelligence Service Unreachable
The `analyze_task_multi.py` retries 3 times with exponential backoff:
- Attempt 1: immediate
- Attempt 2: wait 2s
- Attempt 3: wait 4s

If all fail, the transcript is saved but not analyzed. You can manually trigger:
```bash
curl -X POST "https://jarvis-intelligence-service-xxx.run.app/api/v1/process/{transcript_id}"
```

### Modal Failures
Transcription backend has automatic fallback:
1. Try Modal (GPU)
2. Try External GPU (if configured)
3. Fall back to local CPU

---

## 📡 Webhook Renewal

Google Drive webhooks expire after 24 hours. Cloud Scheduler calls `/renew-webhook` daily:

```bash
# Manual renewal if needed
curl -X POST https://jarvis-audio-pipeline-xxx.run.app/renew-webhook
```

---

## 🛠️ Debugging

### Check Recent Pipeline Runs
```sql
SELECT 
    run_id,
    source_file,
    event_type,
    status,
    message,
    duration_ms,
    created_at
FROM pipeline_logs
ORDER BY created_at DESC
LIMIT 20;
```

### Find Failed Transcripts
```sql
SELECT * FROM pipeline_logs
WHERE status = 'error'
ORDER BY created_at DESC;
```

### Check Specific Run
```sql
SELECT * FROM pipeline_logs
WHERE run_id = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY created_at;
```

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_DRIVE_FOLDER_ID` | Yes | Folder to watch for new files |
| `GOOGLE_DRIVE_PROCESSED_FOLDER_ID` | Yes | Where to move completed files |
| `INTELLIGENCE_SERVICE_URL` | Yes | URL of Intelligence Service |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase service role key |
| `GOOGLE_TOKEN_JSON` | Yes | OAuth credentials as JSON string |
| `TRANSCRIPTION_BACKEND` | No | Force specific backend (modal/external_gpu/local) |
| `EXTERNAL_GPU_URL` | No | URL of external GPU server |

---

## 🚫 DO NOT MODIFY

The following files are critical and should not be changed without extensive testing:

1. **`src/tasks/transcribe_task.py`** - Transcription orchestration
2. **`src/core/transcription_backends/`** - Backend routing logic
3. **`modal_whisperx_v2.py`** - Modal function (deployed separately)
4. **`src/supabase/multi_db.py`** - Database operations

---

## ✅ Safe to Modify

- `cloud_run_server.py` - Add new endpoints (with caution)
- Error messages and logging
- Retry counts and timeouts

---

## 🔗 Related Services

| Service | Role | Communication |
|---------|------|---------------|
| **jarvis-intelligence-service** | Analyzes transcripts, creates meetings/tasks | Receives POST /api/v1/process/{id} |
| **jarvis-telegram-bot** | User interface for voice memos | Calls POST /process/upload |
| **jarvis-sync-service** | Syncs analyzed data to Notion | Reads from same Supabase tables |
