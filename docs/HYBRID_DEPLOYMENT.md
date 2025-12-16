# Jarvis Hybrid Cloud Deployment Guide

Deploy Jarvis with GPU-accelerated transcription using your own hardware or Modal.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Cloud Run / Docker                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Airflow Orchestration (Slim)                │   │
│  │  • Google Drive monitoring                               │   │
│  │  • Audio download                                        │   │
│  │  • LLM analysis (Claude)                                 │   │
│  │  • Notion export                                         │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │                                      │
└───────────────────────────┼──────────────────────────────────────┘
                            │ Transcription Request (HTTP)
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
  ┌─────────────────────┐       ┌─────────────────────┐
  │   External GPU      │       │      Modal          │
  │   (Your Laptop)     │       │   (Serverless)      │
  │                     │       │                     │
  │  • WhisperX         │       │  • WhisperX         │
  │  • NVIDIA GPU       │       │  • T4/L4/A100 GPU   │
  │  • FREE!            │       │  • Pay-per-use      │
  │  • ~2-5x realtime   │       │  • ~10-20x realtime │
  └─────────────────────┘       └─────────────────────┘
```

## Backend Priority

The system automatically selects the best available backend:

1. **External GPU** - Your laptop/workstation (FREE, best if available)
2. **Modal** - Serverless cloud GPU (pay-per-use fallback)
3. **Local CPU** - Last resort (slow but always works)

## Option 1: External GPU Server (Your NVIDIA Laptop)

Perfect for: Regular use, zero cloud costs

### On Your GPU Laptop

```bash
# Clone Jarvis (or copy files)
cd /path/to/Jarvis

# Install GPU server dependencies
pip install -r requirements-gpu-server.txt

# Get HuggingFace token for speaker diarization
# https://huggingface.co/settings/tokens
export HUGGINGFACE_TOKEN=hf_xxxxxxxxx

# Start the server
python -m src.core.transcription_backends.external_server \
    --host 0.0.0.0 \
    --port 8000 \
    --hf-token $HUGGINGFACE_TOKEN

# Output:
# Loading WhisperX model: large-v3
# Device: CUDA (float16)
# GPU: NVIDIA GeForce RTX 3080 (10.0 GB)
# ✓ Model loaded and ready
# Starting server on http://0.0.0.0:8000
```

### On Airflow (Cloud)

```bash
# Point to your GPU laptop
export EXTERNAL_GPU_URL=http://192.168.1.100:8000
```

### Security Options

For remote access, use one of:

1. **Tailscale VPN** (recommended)
   ```bash
   # Install Tailscale on both machines
   # Use Tailscale IP: EXTERNAL_GPU_URL=http://100.x.x.x:8000
   ```

2. **SSH Tunnel**
   ```bash
   ssh -L 8000:localhost:8000 user@your-laptop
   # Then use: EXTERNAL_GPU_URL=http://localhost:8000
   ```

3. **API Key Authentication**
   ```bash
   # On laptop
   python -m src.core.transcription_backends.external_server \
       --api-key your-secret-key
   
   # On Airflow
   export EXTERNAL_GPU_API_KEY=your-secret-key
   ```

## Option 2: Modal (Serverless GPU)

Perfect for: Occasional use, burst capacity, no local GPU

### Setup Modal

```bash
# Install Modal CLI
pip install modal

# Authenticate (opens browser)
modal token new

# Create HuggingFace secret in Modal dashboard
# https://modal.com/secrets
# Name: huggingface-token  
# Key: HUGGINGFACE_TOKEN = hf_xxxxxxxxx
```

### Enable in Airflow

```bash
export MODAL_ENABLED=true
export MODAL_GPU_TYPE=T4  # Options: T4 ($0.59/hr), L4 ($0.80/hr), A100 ($3.00/hr)
```

### Costs

| GPU Type | Price/Hour | 30-min Audio | 60-min Audio |
|----------|------------|--------------|--------------|
| T4       | $0.59      | ~$0.03       | ~$0.06       |
| L4       | $0.80      | ~$0.04       | ~$0.08       |
| A100     | $3.00      | ~$0.15       | ~$0.30       |

*Assumes ~10-20x realtime processing speed*

## Option 3: Hybrid (Both Backends)

Use your laptop when online, Modal when offline:

```bash
# Configure both
export EXTERNAL_GPU_URL=http://your-laptop:8000
export MODAL_ENABLED=true

# Transcription router automatically:
# 1. Tries external GPU first
# 2. Falls back to Modal if laptop unreachable
# 3. Uses local CPU as last resort
```

## Slim Docker Image for Cloud Run

### Build Slim Image

```bash
# Build (no WhisperX, ~500MB instead of 8GB)
docker build -f Dockerfile.slim -t jarvis-airflow:slim .

# Test locally
docker run -p 8080:8080 \
    -e EXTERNAL_GPU_URL=http://host.docker.internal:8000 \
    jarvis-airflow:slim
```

### Deploy to Cloud Run

```bash
# Tag and push to GCR
docker tag jarvis-airflow:slim gcr.io/PROJECT_ID/jarvis-airflow:slim
docker push gcr.io/PROJECT_ID/jarvis-airflow:slim

# Deploy
gcloud run deploy jarvis-airflow \
    --image gcr.io/PROJECT_ID/jarvis-airflow:slim \
    --region us-central1 \
    --memory 1Gi \
    --cpu 1 \
    --set-env-vars "EXTERNAL_GPU_URL=http://your-tailscale-ip:8000,ANTHROPIC_API_KEY=sk-xxx"
```

## Environment Variables Reference

### Airflow/Cloud Run

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSCRIPTION_BACKEND` | auto | Force: `external_gpu`, `modal`, `local` |
| `EXTERNAL_GPU_URL` | - | URL of GPU server (e.g., `http://laptop:8000`) |
| `EXTERNAL_GPU_API_KEY` | - | API key for GPU server auth |
| `MODAL_ENABLED` | true | Enable Modal fallback |
| `MODAL_GPU_TYPE` | T4 | Modal GPU: `T4`, `L4`, `A100` |
| `WHISPER_MODEL` | large-v3 | Whisper model size |
| `ENABLE_DIARIZATION` | true | Speaker identification |
| `ANTHROPIC_API_KEY` | - | Claude API key |
| `NOTION_TOKEN` | - | Notion integration token |

### GPU Server (Laptop)

| Variable | Description |
|----------|-------------|
| `HUGGINGFACE_TOKEN` | Required for speaker diarization |
| `EXTERNAL_GPU_API_KEY` | Optional auth key |

## Testing

### Check Backend Status

```python
from src.core.transcription_backends import get_transcription_router

router = get_transcription_router()
print(router.get_status())
# {
#   'backends': {
#     'external_gpu': {'available': True, 'server_url': 'http://...'},
#     'modal': {'available': True},
#     'local': {'available': True, 'device': 'cpu'}
#   }
# }
```

### Test Transcription

```python
from pathlib import Path
result = router.transcribe(Path("test_audio.mp3"))
print(f"Backend: {result.backend}, Time: {result.processing_time:.1f}s")
```

### Test GPU Server Directly

```bash
# Health check
curl http://localhost:8000/health

# Server info
curl http://localhost:8000/info

# Transcribe
curl -X POST http://localhost:8000/transcribe \
    -F "file=@audio.mp3" \
    -F "enable_diarization=true"
```

## Cost Comparison

| Setup | Monthly Cost* | Best For |
|-------|---------------|----------|
| External GPU only | $5-15 (hosting only) | Regular use, own hardware |
| Modal only | $15-50 | No local GPU, occasional use |
| Hybrid | $5-20 | Best reliability |

*Assumes Cloud Run hosting + 20 hours transcription/month*

## Troubleshooting

### External GPU Not Detected

```bash
# Check server is running
curl http://laptop-ip:8000/health

# Check firewall
# Windows: Allow python.exe through Windows Firewall
# Linux: sudo ufw allow 8000

# Check network connectivity
ping laptop-ip
```

### Modal Authentication Failed

```bash
# Re-authenticate
modal token new

# Check token exists
cat ~/.modal.toml

# For CI/CD, set env vars:
export MODAL_TOKEN_ID=xxx
export MODAL_TOKEN_SECRET=xxx
```

### Slow Transcription

Check logs for "Using backend: ..." message:
- `external_gpu` → Fast (2-5x realtime)
- `modal` → Fast (10-20x realtime)  
- `local` → Slow (0.1x realtime on CPU)

If falling back to local, check GPU backends.

## Files

```
Jarvis/
├── Dockerfile.slim              # Cloud Run image (~500MB)
├── requirements-slim.txt        # No WhisperX
├── requirements-gpu-server.txt  # GPU laptop deps
└── src/core/transcription_backends/
    ├── router.py               # Smart backend selection
    ├── external_backend.py     # HTTP client
    ├── external_server.py      # FastAPI GPU server
    ├── modal_backend.py        # Modal integration
    └── local_backend.py        # CPU fallback
```
