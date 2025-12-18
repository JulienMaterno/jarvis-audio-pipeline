# 🤖 Jarvis - AI Audio Processing Pipeline

> The ingestion engine for the Jarvis ecosystem. Automatically transcribes audio using Modal (GPU) and sends it to the Intelligence Service.

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
```

**Required Environment Variables (.env):**
```ini
# Google Drive
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
GOOGLE_DRIVE_PROCESSED_FOLDER_ID=your_processed_folder_id

# Modal (Transcription)
MODAL_TOKEN_ID=your_modal_token
MODAL_TOKEN_SECRET=your_modal_secret

# Intelligence Service (The API we call after transcription)
INTELLIGENCE_SERVICE_URL=https://your-cloud-run-url.run.app
INTELLIGENCE_SERVICE_TOKEN=optional_if_auth_needed

# Supabase (For logging pipeline events)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

### 2. Google Drive Setup
1. Create a folder in Google Drive (e.g., "Jarvis Audio").
2. Create a subfolder named "Processed".
3. Get the IDs from the URL of both folders.
4. Place `credentials.json` (Service Account or OAuth) in `data/credentials.json`.

### 3. Running the Pipeline

**Manual Run (Process all files once):**
```bash
python run_pipeline.py
```

**Daemon Mode (Watch for new files):**
```bash
python run_pipeline.py --daemon
```

## 🔄 Pipeline Flow

1.  **Monitor**: Checks Google Drive for new audio files.
2.  **Download**: Downloads the file locally.
3.  **Transcribe**: Sends audio to **Modal** (serverless GPU) for WhisperX transcription.
4.  **Save**: Saves the raw transcript to Supabase.
5.  **Handoff**: Calls the **Intelligence Service** API with the transcript ID to trigger analysis.
6.  **Cleanup**: Moves the audio file to the "Processed" folder in Drive.

## 🛠️ Tech Stack
*   **Python 3.10+**
*   **Modal**: Serverless GPU for WhisperX (fast & accurate transcription).
*   **Google Drive API**: File storage and monitoring.
*   **Supabase**: Database for tracking pipeline state.
