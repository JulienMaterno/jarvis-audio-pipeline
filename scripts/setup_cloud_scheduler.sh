#!/bin/bash
# ============================================================================
# Cloud Scheduler Setup for Jarvis Audio Pipeline
# ============================================================================
# This script creates a Cloud Scheduler job that triggers the audio pipeline
# every 15 minutes to process new voice memos from Google Drive.
#
# Prerequisites:
# - gcloud CLI installed and authenticated
# - Cloud Scheduler API enabled
# - Cloud Run service deployed
# ============================================================================

PROJECT_ID="jarvis-436612"
REGION="asia-southeast1"
SERVICE_NAME="jarvis-audio-pipeline"
JOB_NAME="jarvis-audio-pipeline-trigger"

# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region=$REGION \
    --format="value(status.url)" \
    --project=$PROJECT_ID)

if [ -z "$SERVICE_URL" ]; then
    echo "Error: Could not find Cloud Run service $SERVICE_NAME"
    exit 1
fi

echo "Found service URL: $SERVICE_URL"

# Create a service account for the scheduler (if not exists)
SA_NAME="cloud-scheduler-invoker"
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"

echo "Checking service account..."
if ! gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT_ID 2>/dev/null; then
    echo "Creating service account..."
    gcloud iam service-accounts create $SA_NAME \
        --display-name="Cloud Scheduler Invoker" \
        --project=$PROJECT_ID
fi

# Grant the service account permission to invoke Cloud Run
echo "Granting Cloud Run invoker permission..."
gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --region=$REGION \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/run.invoker" \
    --project=$PROJECT_ID

# Delete existing job if it exists
echo "Checking for existing job..."
if gcloud scheduler jobs describe $JOB_NAME --location=$REGION --project=$PROJECT_ID 2>/dev/null; then
    echo "Deleting existing job..."
    gcloud scheduler jobs delete $JOB_NAME \
        --location=$REGION \
        --project=$PROJECT_ID \
        --quiet
fi

# Create the scheduler job - runs every 15 minutes
echo "Creating Cloud Scheduler job..."
gcloud scheduler jobs create http $JOB_NAME \
    --location=$REGION \
    --schedule="*/15 * * * *" \
    --uri="$SERVICE_URL/process" \
    --http-method=POST \
    --oidc-service-account-email=$SA_EMAIL \
    --oidc-token-audience=$SERVICE_URL \
    --attempt-deadline=900s \
    --project=$PROJECT_ID

echo ""
echo "============================================================================"
echo "Cloud Scheduler job created successfully!"
echo "============================================================================"
echo "Job Name: $JOB_NAME"
echo "Schedule: Every 15 minutes"
echo "Target: $SERVICE_URL/process"
echo ""
echo "To test manually:"
echo "  gcloud scheduler jobs run $JOB_NAME --location=$REGION --project=$PROJECT_ID"
echo ""
echo "To view logs:"
echo "  gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME' --limit=50 --project=$PROJECT_ID"
echo "============================================================================"
