# Webhook Setup Guide

This guide explains how to set up Google Drive webhooks for instant file processing, replacing the 15-minute polling with <1 second notifications.

## Architecture Overview

```
Google Drive → Webhook Notification → Flask Server → Airflow API → DAG Trigger
```

When a file is uploaded to your Google Drive folder, Google sends a webhook notification to your server, which immediately triggers the Airflow DAG for processing.

## Prerequisites

- Docker containers running (`docker-compose up -d`)
- Google Drive API credentials configured
- Public URL for webhook endpoint (ngrok for local, or cloud deployment)

## Setup Steps

### 1. Expose Webhook Endpoint

**Option A: Local Development with ngrok**
```powershell
# Install ngrok (if not already installed)
# Download from https://ngrok.com/download

# Start ngrok tunnel
ngrok http 5000

# You'll see output like:
# Forwarding https://abc123.ngrok-free.app -> http://localhost:5000
```

**Option B: Cloud Deployment**
Deploy to a cloud provider (AWS, GCP, Azure, DigitalOcean) and use the public URL.

### 2. Update Environment Variables

Edit `.env` file with your webhook URL:

```dotenv
WEBHOOK_URL=https://abc123.ngrok-free.app/google-drive-webhook
WEBHOOK_SECRET=your-secure-random-secret-key-here
```

Generate a secure secret:
```powershell
# PowerShell command to generate random secret
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 }))
```

### 3. Restart Webhook Container

```powershell
cd "c:\Users\aaron\My Drive\Jarvis\Jarvis"
docker-compose restart jarvis-webhook
```

### 4. Verify Webhook Registration

Check logs to confirm webhook is registered:
```powershell
docker logs jarvis-webhook -f
```

You should see:
```
INFO:__main__:Webhook registered successfully with channel ID: ...
INFO:__main__:Webhook will expire on: 2025-12-03 14:30:00
INFO:apscheduler.scheduler:Added job "renew_webhook" to job store "default"
```

### 5. Test the Webhook

1. Upload an audio file to your Google Drive folder
2. Watch webhook logs for notification:
   ```powershell
   docker logs jarvis-webhook -f
   ```
3. Check Airflow UI at http://localhost:8080 to see DAG triggered
4. Monitor processing in Airflow logs

## How It Works

### Webhook Registration
- Flask server registers webhook with Google Drive API on startup
- Google sends notifications to your `WEBHOOK_URL` when files change
- Webhook expires after 7 days (Google limitation)

### Automatic Renewal
- BackgroundScheduler runs every 6 days (before expiration)
- Automatically renews webhook registration
- No manual intervention needed

### Security
- Webhook notifications include Google signature in headers
- Server verifies signature using `WEBHOOK_SECRET`
- Prevents unauthorized trigger attempts

### DAG Triggering
- Webhook server calls Airflow REST API
- Triggers `jarvis_audio_processing_multi` DAG
- Processing starts within 1 second of file upload

## Configuration Reference

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `WEBHOOK_URL` | Public URL for webhook notifications | `https://abc123.ngrok-free.app/google-drive-webhook` |
| `WEBHOOK_SECRET` | Secret key for signature verification | `your-secure-random-key` |
| `AIRFLOW_API_URL` | Airflow REST API endpoint | `http://localhost:8080/api/v1` |
| `AIRFLOW_USERNAME` | Airflow admin username | `admin` |
| `AIRFLOW_PASSWORD` | Airflow admin password | `admin` |
| `GOOGLE_DRIVE_FOLDER_ID` | Folder ID to watch | `1cTsGDNwVhmgcLx7JZtvrei8EFUQ7lwPc` |

### Webhook Server Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/google-drive-webhook` | POST | Receives Google Drive notifications |
| `/health` | GET | Health check endpoint |

## Troubleshooting

### Webhook Not Receiving Notifications

1. **Check webhook registration status:**
   ```powershell
   docker logs jarvis-webhook --tail 50
   ```

2. **Verify public URL is accessible:**
   ```powershell
   curl https://your-domain.com/google-drive-webhook
   ```

3. **Check Google Drive API quota:**
   - Go to Google Cloud Console
   - Navigate to APIs & Services → Dashboard
   - Check Drive API usage

### Webhook Expired

If webhook expires before renewal:
```powershell
# Restart webhook container to re-register
docker-compose restart jarvis-webhook
```

### DAG Not Triggering

1. **Check Airflow API credentials:**
   ```powershell
   # Test API access
   $cred = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin"))
   curl -H "Authorization: Basic $cred" http://localhost:8080/api/v1/dags
   ```

2. **Verify DAG is active:**
   - Open Airflow UI: http://localhost:8080
   - Check `jarvis_audio_processing_multi` is enabled
   - Look for recent DAG runs

### ngrok Tunnel Issues

If ngrok disconnects:
```powershell
# Restart ngrok
ngrok http 5000

# Update WEBHOOK_URL in .env with new URL
# Restart webhook container
docker-compose restart jarvis-webhook
```

## Performance Comparison

### Before (Polling)
- Check interval: 15 minutes
- Average latency: 7.5 minutes (0-15 minute range)
- CPU usage: Constant checking every 15 minutes
- Max concurrent: 3 files

### After (Webhook)
- Notification latency: <1 second
- Processing start: Immediate
- CPU usage: Idle until file uploaded
- Max concurrent: 3 files (unchanged)

## Migration Path

The webhook system is now active. The DAG no longer runs on a schedule:

**Old Configuration:**
```python
schedule_interval=timedelta(minutes=15)
```

**New Configuration:**
```python
schedule_interval=None  # Webhook-triggered only
```

Files uploaded to Google Drive will now trigger processing instantly instead of waiting up to 15 minutes.

## Next Steps

1. **Monitor webhook renewal:** Check logs every 6 days to confirm auto-renewal
2. **Production deployment:** Replace ngrok with permanent cloud URL
3. **Add monitoring:** Set up alerts for webhook failures
4. **Test failover:** Ensure system handles webhook expiration gracefully

## Additional Resources

- [Google Drive Push Notifications](https://developers.google.com/drive/api/guides/push)
- [Airflow REST API](https://airflow.apache.org/docs/apache-airflow/stable/stable-rest-api-ref.html)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
