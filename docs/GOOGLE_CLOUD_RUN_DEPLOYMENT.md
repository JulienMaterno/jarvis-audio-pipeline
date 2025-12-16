# Google Cloud Run Deployment Guide

Complete guide to deploying Jarvis on Google Cloud Run with GPU support for instant audio transcription.

## Overview

**Architecture:**
```
Google Drive → Webhook → Cloud Run (GPU) → Cloud SQL → Notion
                              ↓
                         WhisperX + Claude
```

**Benefits:**
- ✅ Serverless (pay only when processing)
- ✅ GPU acceleration (15-20x realtime transcription)
- ✅ Auto-scaling (handles multiple files simultaneously)
- ✅ Instant webhooks (<1 second notification)
- ✅ No server maintenance
- ✅ $135-145/month for 10 hours audio/day

## Prerequisites

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed: https://cloud.google.com/sdk/docs/install
3. **Docker** installed: https://docs.docker.com/get-docker/
4. **Git** repository with Jarvis code

## Quick Start (30 minutes)

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd Jarvis
```

### 2. Set Up Google Cloud Project
```bash
# Create new project (or use existing)
PROJECT_ID="jarvis-production"
gcloud projects create ${PROJECT_ID}
gcloud config set project ${PROJECT_ID}

# Enable billing (required for Cloud Run GPU)
# https://console.cloud.google.com/billing/linkedaccount?project=${PROJECT_ID}
```

### 3. Set Up Secrets
```bash
# Make script executable
chmod +x setup-secrets.sh

# Run setup (will prompt for API keys)
./setup-secrets.sh ${PROJECT_ID}
```

**Required secrets:**
- `google-credentials-json` - Google Drive API credentials
- `google-token-json` - Google Drive OAuth token
- `claude-api-key` - Claude API key
- `notion-api-key` - Notion API key
- `huggingface-token` - HuggingFace token (for speaker diarization)

### 4. Create Cloud SQL Database
```bash
# Create PostgreSQL instance
gcloud sql instances create jarvis-db \
    --tier=db-f1-micro \
    --region=us-central1 \
    --database-version=POSTGRES_13 \
    --storage-size=10GB \
    --storage-type=SSD

# Create database
gcloud sql databases create airflow --instance=jarvis-db

# Create user
gcloud sql users create airflow \
    --instance=jarvis-db \
    --password=<secure-password>

# Get connection name
INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe jarvis-db --format='value(connectionName)')
echo "Connection: ${INSTANCE_CONNECTION_NAME}"
```

### 5. Deploy to Cloud Run
```bash
# Make script executable
chmod +x deploy-cloudrun.sh

# Deploy (takes 10-15 minutes for first build)
./deploy-cloudrun.sh ${PROJECT_ID} us-central1
```

### 6. Configure Database Connection
```bash
# Update service with Cloud SQL connection
gcloud run services update jarvis-scheduler \
    --region=us-central1 \
    --add-cloudsql-instances=${INSTANCE_CONNECTION_NAME} \
    --set-env-vars="AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:<password>@/airflow?host=/cloudsql/${INSTANCE_CONNECTION_NAME}"
```

### 7. Initialize Airflow Database
```bash
# Run one-time job to initialize database
gcloud run jobs create jarvis-init \
    --image=gcr.io/${PROJECT_ID}/jarvis:latest \
    --region=us-central1 \
    --add-cloudsql-instances=${INSTANCE_CONNECTION_NAME} \
    --set-env-vars="AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:<password>@/airflow?host=/cloudsql/${INSTANCE_CONNECTION_NAME}" \
    --command=bash,-c,"airflow db migrate && airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@jarvis.local"

# Execute job
gcloud run jobs execute jarvis-init --region=us-central1 --wait
```

### 8. Set Up Webhook
```bash
# Get Cloud Run service URL
SERVICE_URL=$(gcloud run services describe jarvis-scheduler --region=us-central1 --format='value(status.url)')
echo "Webhook URL: ${SERVICE_URL}/google-drive-webhook"

# Update webhook configuration
gcloud run services update jarvis-scheduler \
    --region=us-central1 \
    --set-env-vars="WEBHOOK_URL=${SERVICE_URL}/google-drive-webhook"
```

### 9. Test Deployment
```bash
# View logs
gcloud run services logs read jarvis-scheduler --region=us-central1 --follow

# Upload test file to Google Drive
# Watch logs for processing
```

## Configuration

### Environment Variables

Set via Cloud Run console or CLI:

```bash
gcloud run services update jarvis-scheduler \
    --region=us-central1 \
    --set-env-vars="
        WHISPER_MODEL=large-v3,
        ENABLE_DIARIZATION=true,
        GOOGLE_DRIVE_FOLDER_ID=<your-folder-id>,
        GOOGLE_DRIVE_PROCESSED_FOLDER_ID=<your-processed-folder-id>,
        NOTION_MEETING_DATABASE_ID=<your-meeting-db-id>,
        NOTION_CRM_DATABASE_ID=<your-crm-db-id>,
        NOTION_TASKS_DATABASE_ID=<your-tasks-db-id>,
        NOTION_REFLECTIONS_DATABASE_ID=<your-reflections-db-id>
    "
```

### GPU Configuration

**Available GPU types:**
- `nvidia-l4` - Best price/performance ($0.70/hr)
- `nvidia-tesla-t4` - Budget option ($0.50/hr)
- `nvidia-a100` - Maximum performance ($2.50/hr)

**Change GPU type:**
```bash
gcloud run services update jarvis-scheduler \
    --region=us-central1 \
    --gpu-type=nvidia-l4
```

### Scaling Configuration

```bash
gcloud run services update jarvis-scheduler \
    --region=us-central1 \
    --min-instances=0 \
    --max-instances=3 \
    --concurrency=1
```

- `min-instances=0` - Scale to zero when idle (no cost)
- `max-instances=3` - Process up to 3 files simultaneously
- `concurrency=1` - One file per container instance

## Monitoring

### View Logs
```bash
# Real-time logs
gcloud run services logs read jarvis-scheduler --region=us-central1 --follow

# Tail last 100 lines
gcloud run services logs read jarvis-scheduler --region=us-central1 --limit=100
```

### Cloud Console
- **Service dashboard**: https://console.cloud.google.com/run
- **Logs explorer**: https://console.cloud.google.com/logs
- **Metrics**: https://console.cloud.google.com/monitoring

### Set Up Alerts
```bash
# Alert on errors
gcloud alpha monitoring policies create \
    --notification-channels=<channel-id> \
    --display-name="Jarvis Error Alert" \
    --condition-display-name="Error rate > 5%" \
    --condition-threshold-value=0.05 \
    --condition-threshold-duration=300s
```

## Cost Optimization

### Current Costs (~$43-50/month with Haiku)
- GPU compute: $20-30/month (serverless, pay-per-use)
- Cloud SQL: $10/month (db-f1-micro)
- Claude Haiku API: $8/month (10 hrs audio/day)
- Storage: $2/month
- Networking: $3/month

### Optimization Tips

**1. Already Using Haiku (90% Savings vs Sonnet)** ✅
```bash
# Current configuration uses Claude Haiku ($8/month vs $95/month Sonnet)
CLAUDE_MODEL=claude-haiku-20240307

# Switch to Sonnet only if you need better reasoning:
CLAUDE_MODEL=claude-sonnet-4-5-20250929
```
- Process multiple files together
- Reduces cold start overhead
- Better GPU utilization

**3. Use Claude Haiku for Simple Tasks**
```bash
# Update environment variable
CLAUDE_MODEL=claude-haiku-20240307  # $0.25/M tokens (90% savings)
```

**4. Compress Audio Files**
```bash
# Use Opus codec (50% smaller)
# Saves on storage and transfer costs
```

**5. Regional Selection**
```bash
# Use cheapest region
# us-central1 often has best pricing
```

## Troubleshooting

### Cold Start Issues
**Problem**: First request takes 30-60 seconds

**Solution**: Set min-instances=1
```bash
gcloud run services update jarvis-scheduler \
    --region=us-central1 \
    --min-instances=1  # Costs ~$50/month extra
```

### GPU Not Available
**Problem**: "GPU not available" error

**Solution**: Check quota
```bash
# View quotas
gcloud compute project-info describe --project=${PROJECT_ID}

# Request quota increase
# https://console.cloud.google.com/iam-admin/quotas
```

### Database Connection Issues
**Problem**: "Could not connect to database"

**Solution**: Verify Cloud SQL proxy
```bash
# Check connection name
gcloud sql instances describe jarvis-db --format='value(connectionName)'

# Verify service has access
gcloud run services describe jarvis-scheduler --region=us-central1 --format='value(spec.template.spec.containers[0].cloudsqlInstances)'
```

### Out of Memory
**Problem**: Container killed (OOMKilled)

**Solution**: Increase memory
```bash
gcloud run services update jarvis-scheduler \
    --region=us-central1 \
    --memory=16Gi  # Increase from 8Gi
```

### Timeout Issues
**Problem**: Request timeout after 60 seconds

**Solution**: Increase timeout
```bash
gcloud run services update jarvis-scheduler \
    --region=us-central1 \
    --timeout=3600  # 1 hour
```

## Rollback

### Rollback to Previous Version
```bash
# List revisions
gcloud run revisions list --service=jarvis-scheduler --region=us-central1

# Rollback
gcloud run services update-traffic jarvis-scheduler \
    --region=us-central1 \
    --to-revisions=<revision-name>=100
```

## Cleanup

### Delete All Resources
```bash
# Delete Cloud Run service
gcloud run services delete jarvis-scheduler --region=us-central1

# Delete Cloud SQL instance
gcloud sql instances delete jarvis-db

# Delete container images
gcloud container images delete gcr.io/${PROJECT_ID}/jarvis:latest

# Delete secrets
gcloud secrets delete google-credentials-json
gcloud secrets delete google-token-json
gcloud secrets delete claude-api-key
gcloud secrets delete notion-api-key
gcloud secrets delete huggingface-token

# Delete project (WARNING: irreversible!)
gcloud projects delete ${PROJECT_ID}
```

## Next Steps

1. **Set up monitoring alerts** for errors and high costs
2. **Configure backup strategy** for Cloud SQL
3. **Test webhook failover** scenarios
4. **Optimize Claude prompts** to reduce API costs
5. **Enable Cloud Armor** for DDoS protection

## Support

- **Google Cloud Support**: https://cloud.google.com/support
- **Jarvis Issues**: <your-github-repo>/issues
- **Community**: <your-discord/slack>

## Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud SQL Best Practices](https://cloud.google.com/sql/docs/postgres/best-practices)
- [GPU on Cloud Run](https://cloud.google.com/run/docs/configuring/gpu)
- [Secret Manager Guide](https://cloud.google.com/secret-manager/docs)
