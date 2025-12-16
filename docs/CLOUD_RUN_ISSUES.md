# Google Cloud Run Deployment - Issues & Fixes

## Issues Found & Resolutions

### ✅ 1. **Docker Compose Not Supported on Cloud Run**
**Issue**: Cloud Run doesn't support docker-compose (multi-container setups)

**Solution**: Deploy as separate services
- Airflow Scheduler → Cloud Run service with GPU
- PostgreSQL → Cloud SQL (managed database)
- Webhook server → Same container as scheduler (Flask endpoint)

---

### ✅ 2. **Volume Mounts Don't Persist**
**Issue**: Cloud Run containers are ephemeral - volumes reset on restart

**Affected**:
- `whisper-cache` volume (WhisperX models ~3GB)
- `temp` directory (audio files)
- `logs` directory
- `token.json` (Google Drive auth)

**Solution**:
- **Whisper models**: Download on startup (cached in container during build)
- **Audio files**: Store in Google Cloud Storage bucket, not local temp
- **Logs**: Send to Cloud Logging (built-in)
- **token.json**: Store in Secret Manager

---

### ✅ 3. **File Paths Use Relative Paths**
**Issue**: Some paths assume local filesystem structure

**Locations**:
```python
# src/config.py
TEMP_AUDIO_DIR = PROJECT_ROOT / Path(os.getenv('TEMP_AUDIO_DIR', 'temp'))
LOG_DIR = PROJECT_ROOT / Path(os.getenv('LOG_DIR', 'logs'))

# src/core/transcriber.py
cache_dir = os.getenv('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))

# src/core/speaker_identifier.py
self.speaker_identifier.load_profiles("data/voice_profiles")
```

**Solution**: Already handled via environment variables! Just need to set:
```
XDG_CACHE_HOME=/opt/cache
TEMP_AUDIO_DIR=/tmp/jarvis/audio
LOG_DIR=/tmp/jarvis/logs
```

---

### ✅ 4. **Google Drive Credentials Mount**
**Issue**: Credentials mounted as files won't work on Cloud Run

**Current**:
```yaml
volumes:
  - ./data/credentials.json:/opt/jarvis/data/credentials.json
  - ./data/token.json:/opt/jarvis/data/token.json
```

**Solution**: Use Secret Manager
```python
# Instead of file path, load from environment
credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
token_json = os.getenv('GOOGLE_TOKEN_JSON')
```

---

### ✅ 5. **GPU Support Configuration**
**Issue**: Cloud Run GPU requires specific configuration

**Current**: Auto-detects GPU
```python
self.device = "cuda" if torch.cuda.is_available() else "cpu"
```

**Solution**: ✅ Already correct! Cloud Run will expose GPU via CUDA

---

### ✅ 6. **Airflow Database Connection**
**Issue**: PostgreSQL container won't exist

**Current**:
```
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
```

**Solution**: Use Cloud SQL
```
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:password@/airflow?host=/cloudsql/PROJECT:REGION:INSTANCE
```

---

### ✅ 7. **Build Tools Installation**
**Issue**: Installing gcc/g++ on every startup is slow

**Current**:
```bash
apt-get update && apt-get install -y gcc g++ make
```

**Solution**: Add to Dockerfile (build-time, not runtime)

---

### ✅ 8. **Webhook Server Port**
**Issue**: Cloud Run requires listening on PORT environment variable

**Current**: `port=5000` (hardcoded)

**Solution**:
```python
port = int(os.getenv('PORT', 5000))
app.run(host='0.0.0.0', port=port)
```

---

### ✅ 9. **Temp File Cleanup**
**Issue**: `/tmp` on Cloud Run is limited to ~2GB

**Risk**: 10 hours audio/day = ~1-2GB. Could fill up.

**Solution**: Immediate cleanup after processing
- Already implemented in `cleanup_task.py` ✅
- Just ensure it runs after each file

---

### ✅ 10. **Voice Profiles Persistence**
**Issue**: `data/voice_profiles/aaron.pkl` needs to persist

**Current**: Mounted as volume (won't work on Cloud Run)

**Solution**: 
- Option A: Bake into Docker image during build
- Option B: Store in Cloud Storage, download on startup
- **Recommended**: Bake into image (small file, rarely changes)

---

## Required Code Changes

### 1. Update config.py for Cloud Storage
```python
# Cloud-friendly paths
TEMP_AUDIO_DIR = Path(os.getenv('TEMP_AUDIO_DIR', '/tmp/jarvis/audio'))
LOG_DIR = Path(os.getenv('LOG_DIR', '/tmp/jarvis/logs'))
```

### 2. Update monitor.py for Secret Manager
```python
def _get_credentials(self):
    # Check if running in cloud with secrets
    creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    if creds_json:
        return Credentials.from_authorized_user_info(json.loads(creds_json))
    
    # Fallback to file-based (local dev)
    return Credentials.from_authorized_user_file(self.token_file)
```

### 3. Update webhook_server.py for dynamic port
```python
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
```

### 4. Create Cloud Run Dockerfile
```dockerfile
FROM apache/airflow:2.8.0-python3.11

USER root
# Install build tools and ffmpeg at build time
RUN apt-get update && \
    apt-get install -y gcc g++ make ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

USER airflow
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Pre-download WhisperX models (avoids startup delay)
RUN python -c "import whisperx; whisperx.load_model('large-v3', 'cpu')"

COPY --chown=airflow:root ./src /opt/jarvis/src
COPY --chown=airflow:root ./airflow/dags /opt/airflow/dags
COPY --chown=airflow:root data/voice_profiles /opt/jarvis/data/voice_profiles

RUN mkdir -p /tmp/jarvis/audio /tmp/jarvis/logs /opt/cache && \
    chown -R airflow:root /tmp/jarvis /opt/cache

ENV PYTHONPATH=/opt/jarvis
ENV JARVIS_PATH=/opt/jarvis
ENV XDG_CACHE_HOME=/opt/cache
ENV TEMP_AUDIO_DIR=/tmp/jarvis/audio
ENV LOG_DIR=/tmp/jarvis/logs

WORKDIR /opt/jarvis
CMD ["airflow", "scheduler"]
```

### 5. Cloud Run Configuration (gcloud CLI)
```bash
# Deploy to Cloud Run with GPU
gcloud run deploy jarvis-scheduler \
  --image=gcr.io/YOUR_PROJECT/jarvis:latest \
  --platform=managed \
  --region=us-central1 \
  --gpu=1 \
  --gpu-type=nvidia-l4 \
  --memory=8Gi \
  --cpu=4 \
  --timeout=3600 \
  --set-env-vars="AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://...,CLAUDE_API_KEY=...,NOTION_API_KEY=...,HUGGINGFACE_TOKEN=..." \
  --set-secrets="GOOGLE_CREDENTIALS_JSON=google-creds:latest,GOOGLE_TOKEN_JSON=google-token:latest"
```

---

## Cost Impact of Fixes

### Before Fixes:
- Models download on every cold start: +3-5 minutes, +$0.10 per start
- Multiple containers: Need separate services ($$$)

### After Fixes:
- Models baked in: Instant startup ✅
- Single service: Much cheaper ✅
- Cloud SQL: Managed, reliable ✅

---

## Migration Checklist

- [ ] Update `config.py` paths to use `/tmp/jarvis`
- [ ] Update `monitor.py` to support Secret Manager
- [ ] Update `webhook_server.py` for dynamic PORT
- [ ] Create Cloud Run Dockerfile with pre-downloaded models
- [ ] Upload credentials to Secret Manager
- [ ] Create Cloud SQL PostgreSQL instance
- [ ] Build and push Docker image to GCR
- [ ] Deploy to Cloud Run with GPU
- [ ] Test with sample audio file
- [ ] Set up webhook with Cloud Run URL
- [ ] Monitor costs and performance

---

## Estimated Timeline

1. **Code changes**: 1-2 hours
2. **Dockerfile creation**: 30 minutes
3. **Cloud setup** (SQL, Secrets): 1 hour
4. **First deployment**: 30 minutes
5. **Testing & debugging**: 1-2 hours

**Total**: 4-6 hours for full migration

---

## Next Steps

1. I'll make the code changes for Cloud Run compatibility
2. Create the Cloud Run Dockerfile
3. Provide deployment scripts
4. Test locally with the new configuration

Ready to proceed?
