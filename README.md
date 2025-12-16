# 🤖 Jarvis - AI Audio Processing Pipeline

> Automatically transcribe, analyze, and organize voice notes into Notion

## 🚀 Quick Start

```bash
# 1. Start Docker containers
docker compose up -d

# 2. Access Airflow UI
http://localhost:8080
# Username: admin | Password: admin

# 3. Enable the DAG
# Click "jarvis_audio_processing_multi" → Toggle ON
```

## ✨ How It Works

**Input:** Audio files dropped in Google Drive  
**Output:** Organized Notion pages with transcripts, summaries, and extracted tasks

### Pipeline Flow

```
📁 Google Drive    →    🎙️ Modal GPU     →    🧠 Claude AI    →    📝 Notion
   (monitor)            (transcribe)          (analyze)           (save)
```

1. **Monitor** - Checks Google Drive every 15 minutes for new audio
2. **Transcribe** - Sends to Modal (T4 GPU) for fast Whisper transcription
3. **Analyze** - Claude 3.5 Haiku categorizes and extracts insights
4. **Save** - Routes to correct Notion database + saves transcript files

### Output Databases (Notion)
- **Meetings** - Conversations with others
- **Reflections** - Personal thoughts and ideas  
- **Tasks** - Action items with due dates
- **CRM** - Contact updates

## 📁 Project Structure

```
Jarvis/
├── src/                    # Core source code
│   ├── core/              # Transcription backends
│   ├── analyzers/         # Claude AI analysis
│   ├── notion/            # Notion API integrations
│   └── tasks/             # Airflow task functions
├── airflow/dags/          # Airflow DAG definition
├── scripts/               # Deployment & admin scripts
├── docs/                  # Documentation
├── data/                  # Credentials (gitignored)
├── Transcripts/           # Saved transcripts (local)
└── modal_whisperx_v2.py   # Modal GPU transcription app
```

## 🔧 Configuration

### Environment Variables (`.env`)
```bash
CLAUDE_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-3-5-haiku-20241022
NOTION_API_KEY=secret_...
HUGGINGFACE_TOKEN=hf_...
GOOGLE_DRIVE_FOLDER_ID=...
GOOGLE_DRIVE_PROCESSED_FOLDER_ID=...
```

## 🚢 Deployment Options

### Local Docker (current)
```bash
docker compose up -d
```

### Google Cloud Run
```bash
./scripts/deploy-cloudrun.sh
```

## 💰 Costs

| Component | Cost |
|-----------|------|
| Transcription (Modal) | ~$0.01/minute of audio |
| Analysis (Claude Haiku) | ~$0.01/file |
| **Total** | **~$0.02-0.05 per file** |

## 📊 Monitoring

- **Airflow UI:** http://localhost:8080
- **DAG:** `jarvis_audio_processing_multi`
- **Schedule:** Every 15 minutes
- **Parallel:** Up to 3 files simultaneously

## 🛠️ Development

### Modal Transcription (deployed separately)
```bash
# Deploy/update Modal app
modal deploy modal_whisperx_v2.py

# Test endpoint
curl https://aaron-j-putting--jarvis-whisperx-transcribe-endpoint.modal.run
```

### Test Google Drive Connection
```bash
python test_gdrive_connection.py
```

## 📚 Documentation

- `docs/QUICKSTART.md` - Getting started guide
- `docs/DEPLOYMENT.md` - Deployment options
- `docs/ARCHITECTURE.md` - System design
