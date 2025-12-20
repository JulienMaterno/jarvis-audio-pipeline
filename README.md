# 🎤 Jarvis Audio Pipeline

> **Audio ingestion only.** Monitors Google Drive for audio files, transcribes using Modal (GPU), saves the transcript, then hands off to the Intelligence Service for analysis.

## 🎯 Role in the Ecosystem

This service does **ONE thing well**: audio → text. It does NOT contain any AI/LLM logic.

```
Audio File → Download → Transcribe (Modal) → Save Transcript → Call Intelligence Service → Move to Processed
```

**Why no AI here?** All intelligence lives in the Intelligence Service. This keeps the pipeline simple and focused.

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

# Intelligence Service (Called after transcription)
INTELLIGENCE_SERVICE_URL=https://jarvis-intelligence-service-xxx.run.app

# Supabase (For saving transcripts)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

### 2. Google Drive Setup
1. Create a folder in Google Drive (e.g., "Jarvis Audio").
2. Create a subfolder named "Processed".
3. Get the IDs from the URL of both folders.
4. Place `credentials.json` (Service Account or OAuth) in `data/credentials.json`.

### 3. Deployment (CI/CD)

This service is automatically deployed to **Google Cloud Run** via **Google Cloud Build** whenever code is pushed to the `main` branch.

*   **Trigger**: Push to `main`
*   **Build Config**: `cloudbuild.yaml`
*   **Environment Variables**:
    *   `INTELLIGENCE_SERVICE_URL`: URL of the Intelligence Service (for handoff)
*   **Secrets**: Managed via Google Secret Manager

## 🔄 Pipeline Flow

1.  **Trigger**: Receives webhook from Google Drive (or polls in daemon mode)
2.  **Download**: Downloads the audio file locally
3.  **Transcribe**: Sends audio to **Modal** (serverless GPU) for WhisperX transcription
4.  **Save**: Saves the raw transcript to Supabase `transcripts` table
5.  **Handoff**: Calls **Intelligence Service** (`INTELLIGENCE_SERVICE_URL`) for AI analysis
6.  **Cleanup**: Moves the audio file to the "Processed" folder in Drive

## 🛠️ Tech Stack
*   **Python 3.10+**
*   **Modal**: Serverless GPU for WhisperX (fast & accurate transcription)
*   **Google Drive API**: File storage and monitoring
*   **Supabase**: Database for transcripts
*   **No AI libraries**: All AI is in Intelligence Service
