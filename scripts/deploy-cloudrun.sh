#!/bin/bash
# Deploy Jarvis to Google Cloud Run
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Project selected: gcloud config set project YOUR_PROJECT_ID
#   - APIs enabled: Cloud Run, Cloud Build, Secret Manager

set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="australia-southeast1"
SERVICE_NAME="jarvis-airflow"

echo "🚀 Deploying Jarvis to Cloud Run"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo ""

# Step 1: Create secrets (first time only)
echo "📦 Setting up secrets..."
if ! gcloud secrets describe jarvis-claude-api-key --project=$PROJECT_ID &>/dev/null; then
    echo "Creating secret: jarvis-claude-api-key"
    echo -n "Enter your Claude API key: "
    read -s CLAUDE_KEY
    echo ""
    echo -n "$CLAUDE_KEY" | gcloud secrets create jarvis-claude-api-key --data-file=- --project=$PROJECT_ID
fi

if ! gcloud secrets describe jarvis-notion-api-key --project=$PROJECT_ID &>/dev/null; then
    echo "Creating secret: jarvis-notion-api-key"
    echo -n "Enter your Notion API key: "
    read -s NOTION_KEY
    echo ""
    echo -n "$NOTION_KEY" | gcloud secrets create jarvis-notion-api-key --data-file=- --project=$PROJECT_ID
fi

if ! gcloud secrets describe jarvis-hf-token --project=$PROJECT_ID &>/dev/null; then
    echo "Creating secret: jarvis-hf-token"
    echo -n "Enter your HuggingFace token: "
    read -s HF_TOKEN
    echo ""
    echo -n "$HF_TOKEN" | gcloud secrets create jarvis-hf-token --data-file=- --project=$PROJECT_ID
fi

# Step 2: Build and deploy using Cloud Build
echo ""
echo "🔨 Building and deploying..."
gcloud builds submit --config cloudbuild.yaml

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📍 Access Airflow at:"
gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)'
echo ""
echo "🔐 Default credentials: admin / admin"
