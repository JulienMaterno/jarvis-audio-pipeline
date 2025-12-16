"""
Google Drive webhook server for instant file notifications.
Runs as a separate service alongside Airflow.
"""

import os
import json
import logging
import hmac
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://your-domain.com/google-drive-webhook')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'change-this-secret-key')
AIRFLOW_API_URL = os.getenv('AIRFLOW_API_URL', 'http://localhost:8080/api/v1')
AIRFLOW_USERNAME = os.getenv('AIRFLOW_USERNAME', 'admin')
AIRFLOW_PASSWORD = os.getenv('AIRFLOW_PASSWORD', 'admin')
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

# Store current channel info
current_channel = None


def get_drive_service():
    """Get authenticated Google Drive service."""
    creds = None
    token_path = 'data/token.json'
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
    
    return build('drive', 'v3', credentials=creds)


def setup_drive_webhook():
    """
    Set up Google Drive push notification webhook.
    Returns channel info including expiration time.
    """
    try:
        service = get_drive_service()
        
        # Calculate expiration (7 days from now)
        expiration_time = datetime.utcnow() + timedelta(days=7)
        expiration_ms = int(expiration_time.timestamp() * 1000)
        
        # Create unique channel ID
        channel_id = f'jarvis-audio-{int(datetime.utcnow().timestamp())}'
        
        # Set up webhook
        channel_body = {
            'id': channel_id,
            'type': 'web_hook',
            'address': WEBHOOK_URL,
            'token': WEBHOOK_SECRET,  # Verify webhook authenticity
            'expiration': expiration_ms
        }
        
        # Watch the folder for changes
        channel = service.files().watch(
            fileId=GOOGLE_DRIVE_FOLDER_ID,
            body=channel_body
        ).execute()
        
        logger.info(f"✓ Webhook registered successfully")
        logger.info(f"  Channel ID: {channel['id']}")
        logger.info(f"  Resource ID: {channel['resourceId']}")
        logger.info(f"  Expires: {expiration_time.isoformat()}")
        
        return channel
        
    except Exception as e:
        logger.error(f"Failed to set up webhook: {e}", exc_info=True)
        return None


def stop_drive_webhook(channel_id, resource_id):
    """Stop an existing webhook."""
    try:
        service = get_drive_service()
        
        service.channels().stop(
            body={
                'id': channel_id,
                'resourceId': resource_id
            }
        ).execute()
        
        logger.info(f"✓ Stopped webhook: {channel_id}")
        
    except Exception as e:
        logger.warning(f"Failed to stop webhook: {e}")


def renew_webhook():
    """
    Renew the webhook before it expires.
    Called automatically every 6 days.
    """
    global current_channel
    
    logger.info("Renewing Google Drive webhook...")
    
    # Stop old webhook if exists
    if current_channel:
        stop_drive_webhook(
            current_channel.get('id'),
            current_channel.get('resourceId')
        )
    
    # Create new webhook
    current_channel = setup_drive_webhook()
    
    if current_channel:
        logger.info("✓ Webhook renewal successful")
    else:
        logger.error("❌ Webhook renewal failed")


def trigger_airflow_dag(file_info):
    """
    Trigger Airflow DAG to process new file.
    
    Args:
        file_info: Dict with file details from Google Drive
    """
    try:
        dag_id = 'jarvis_audio_processing'
        run_id = f"webhook_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Trigger DAG via Airflow REST API
        url = f"{AIRFLOW_API_URL}/dags/{dag_id}/dagRuns"
        
        response = requests.post(
            url,
            auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
            json={
                'dag_run_id': run_id,
                'conf': {
                    'triggered_by': 'google_drive_webhook',
                    'file_id': file_info.get('id'),
                    'file_name': file_info.get('name'),
                    'timestamp': datetime.utcnow().isoformat()
                }
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"✓ Triggered DAG run: {run_id}")
            return True
        else:
            logger.error(f"Failed to trigger DAG: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error triggering DAG: {e}", exc_info=True)
        return False


@app.route('/google-drive-webhook', methods=['POST'])
def handle_webhook():
    """
    Handle incoming Google Drive webhook notifications.
    Called by Google when files are added/changed in the watched folder.
    """
    try:
        # Verify the request is from Google
        token = request.headers.get('X-Goog-Channel-Token')
        if token != WEBHOOK_SECRET:
            logger.warning("Webhook received with invalid token")
            return jsonify({'error': 'Invalid token'}), 401
        
        # Get notification details
        channel_id = request.headers.get('X-Goog-Channel-ID')
        resource_id = request.headers.get('X-Goog-Resource-ID')
        resource_state = request.headers.get('X-Goog-Resource-State')
        
        logger.info(f"Webhook notification received:")
        logger.info(f"  Channel: {channel_id}")
        logger.info(f"  State: {resource_state}")
        
        # Only process 'add' or 'update' events
        if resource_state in ['add', 'update']:
            # Get the actual file info from Drive
            service = get_drive_service()
            
            # List recent files in the folder
            results = service.files().list(
                q=f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false",
                orderBy='createdTime desc',
                pageSize=10,
                fields='files(id, name, mimeType, createdTime)'
            ).execute()
            
            files = results.get('files', [])
            
            # Check for audio files added in last minute
            for file in files:
                mime_type = file.get('mimeType', '')
                name = file.get('name', '')
                
                # Check if it's an audio file
                if (mime_type.startswith('audio/') or 
                    name.lower().endswith(('.mp3', '.m4a', '.wav', '.ogg', '.flac'))):
                    
                    created = datetime.fromisoformat(file['createdTime'].replace('Z', '+00:00'))
                    age_seconds = (datetime.now(created.tzinfo) - created).total_seconds()
                    
                    # Only process files added in last 2 minutes (likely the new one)
                    if age_seconds < 120:
                        logger.info(f"📁 New audio file detected: {name}")
                        trigger_airflow_dag(file)
                        break
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    global current_channel
    
    status = {
        'status': 'healthy',
        'webhook_active': current_channel is not None,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if current_channel:
        expiration_ms = current_channel.get('expiration')
        if expiration_ms:
            expiration = datetime.fromtimestamp(int(expiration_ms) / 1000)
            status['webhook_expires'] = expiration.isoformat()
            status['hours_until_expiration'] = (expiration - datetime.utcnow()).total_seconds() / 3600
    
    return jsonify(status), 200


@app.route('/renew', methods=['POST'])
def manual_renew():
    """Manual webhook renewal endpoint (for testing)."""
    renew_webhook()
    return jsonify({'status': 'renewed'}), 200


def start_webhook_server():
    """
    Start the webhook server with automatic renewal.
    Called when the application starts.
    """
    global current_channel
    
    logger.info("=" * 60)
    logger.info("Google Drive Webhook Server Starting")
    logger.info("=" * 60)
    
    # Initial webhook setup
    current_channel = setup_drive_webhook()
    
    if not current_channel:
        logger.error("❌ Failed to set up initial webhook")
        logger.error("   Server will start but webhooks won't work")
        logger.error("   Check your Google Drive credentials and folder ID")
    
    # Set up automatic renewal every 6 days
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        renew_webhook,
        'interval',
        days=6,
        id='webhook_renewal',
        name='Renew Google Drive Webhook',
        next_run_time=datetime.utcnow() + timedelta(days=6)
    )
    scheduler.start()
    
    logger.info("✓ Automatic renewal scheduled (every 6 days)")
    logger.info(f"✓ Webhook endpoint: {WEBHOOK_URL}")
    logger.info("=" * 60)
    
    # Keep scheduler running
    import atexit
    atexit.register(lambda: scheduler.shutdown())


if __name__ == '__main__':
    # Start webhook system
    start_webhook_server()
    
    # Run Flask server with dynamic port (Cloud Run provides PORT env var)
    port = int(os.getenv('PORT', os.getenv('WEBHOOK_PORT', 5000)))
    logger.info(f"Starting webhook server on port {port}")
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False
    )
