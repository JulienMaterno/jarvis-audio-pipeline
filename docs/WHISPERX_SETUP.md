# WhisperX Setup Guide

## What is WhisperX?

WhisperX extends OpenAI's Whisper with:
- **Speaker Diarization** - Identifies "who said what" (Speaker 1, Speaker 2, etc.)
- **Better Timestamps** - More accurate word-level timing
- **Faster Processing** - Optimized for batch processing

## Prerequisites

### 1. HuggingFace Account (for Speaker Diarization)

**Required for:** Identifying different speakers in conversations

1. Go to https://huggingface.co/join
2. Create a free account
3. Navigate to https://huggingface.co/settings/tokens
4. Click "New token" → "Read" access
5. Copy the token (starts with `hf_...`)

### 2. Accept Diarization Model Terms

1. Visit: https://huggingface.co/pyannote/speaker-diarization-3.1
2. Click "Agree and access repository"
3. Visit: https://huggingface.co/pyannote/segmentation-3.0
4. Click "Agree and access repository"

## Configuration

### Local Development

Add to your `.env` file:
```bash
HUGGINGFACE_TOKEN=hf_your_token_here
WHISPER_MODEL=large-v3
ENABLE_DIARIZATION=true
```

### Cloud Deployment

Add to your cloud secrets manager:
```bash
# AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id jarvis/production \
  --secret-string '{"HUGGINGFACE_TOKEN":"hf_..."}'

# GCP Secret Manager
echo "hf_..." | gcloud secrets create huggingface-token --data-file=-
```

Update `docker-compose.prod.yml`:
```yaml
environment:
  HUGGINGFACE_TOKEN: ${HUGGINGFACE_TOKEN}
  WHISPER_MODEL: large-v3
  ENABLE_DIARIZATION: 'true'
```

## How It Works

### Without Diarization (old):
```
[00:00 - 00:15] Hey, how was your weekend?
[00:15 - 00:30] It was great! I went hiking.
```

### With Diarization (new):
```
[Speaker 1]
  [00:00 - 00:15] Hey, how was your weekend?

[Speaker 2]
  [00:15 - 00:30] It was great! I went hiking.
```

## Performance Comparison

### 50-minute Audio File

| Setup | Model | Time | Quality | Cost/Hour |
|-------|-------|------|---------|-----------|
| **CPU (Local)** | medium | 30-45 min | Good | Free |
| **CPU (Local)** | large-v3 | 60-120 min | Excellent | Free |
| **GPU (Cloud)** | large-v3 | 5-8 min | Excellent | $0.50-1.00 |

### GPU Recommendation (Cloud)

For cloud deployment, use GPU instances:
- **AWS**: g4dn.xlarge ($0.526/hr) - 10-15x faster
- **GCP**: n1-standard-4 + T4 GPU ($0.35/hr + $0.35/hr)
- **Azure**: Standard_NC6 ($0.90/hr)

**Cost analysis for 50min audio:**
- CPU: Free but 60-120min processing
- GPU: $0.10-0.15 per file, 5-8min processing ✅

## Testing Locally (CPU)

For testing without GPU, use smaller model:

```bash
# Edit .env
WHISPER_MODEL=base  # or medium
ENABLE_DIARIZATION=true

# Restart
docker-compose down
docker-compose up -d
```

**CPU Performance:**
- `base`: 15-20 min for 50min audio
- `medium`: 30-45 min for 50min audio
- `large-v3`: 60-120 min for 50min audio (not recommended for CPU)

## Troubleshooting

### "HUGGINGFACE_TOKEN not set"
Solution: Add token to `.env` file

### "Could not load diarization model"
Solution: Accept model terms on HuggingFace (see Prerequisites #2)

### "Diarization disabled"
Check logs:
```bash
docker logs jarvis-scheduler | grep -i diarization
```

If you see "HUGGINGFACE_TOKEN not set", add it to docker-compose.yml:
```yaml
environment:
  HUGGINGFACE_TOKEN: ${HUGGINGFACE_TOKEN}
```

### Transcription too slow
- Use GPU instance in cloud
- OR use smaller model locally (`medium` or `base`)
- OR disable diarization temporarily: `ENABLE_DIARIZATION=false`

## GPU Setup (Cloud Deployment)

### Docker with GPU Support

```bash
# Build with CUDA support
docker build --build-arg CUDA=true -t jarvis-gpu:latest -f Dockerfile .

# Run with GPU
docker run --gpus all jarvis-gpu:latest
```

### Docker Compose with GPU

```yaml
services:
  airflow-scheduler:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Verify GPU Access

```bash
# Check GPU availability
docker exec jarvis-scheduler python -c "import torch; print(torch.cuda.is_available())"

# Should print: True
```

## Benefits of GPU + large-v3

1. **Speed**: 10-15x faster than CPU
2. **Quality**: Best transcription accuracy
3. **Cost-effective**: Shorter runtime = lower compute costs
4. **Speaker ID**: Fast enough to enable diarization for all files

## Next Steps

1. Get HuggingFace token
2. Add to `.env` file
3. Restart containers
4. Test with a meeting recording
5. Check logs for speaker identification
6. Plan cloud GPU deployment

For cloud deployment, see: `docs/CLOUD_DEPLOYMENT.md`
