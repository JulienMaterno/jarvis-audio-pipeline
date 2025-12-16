"""
Cloud Run HTTP wrapper for Jarvis Audio Pipeline.
Exposes the pipeline as an HTTP API - triggered by Cloud Scheduler.
Uses min-instances=0 for cost efficiency.

Supports async processing for large files (2+ hours) via BackgroundTasks.
"""

import os
import logging
import hmac
import hashlib
import asyncio
from fastapi import FastAPI, HTTPException, Request, Header, BackgroundTasks
from contextlib import asynccontextmanager
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('Jarvis.API')

# Reduce noise
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('anthropic').setLevel(logging.WARNING)

# Global pipeline instance
pipeline = None

# Thread pool for background processing
executor = ThreadPoolExecutor(max_workers=2)

# Track processing state
processing_lock = asyncio.Lock()
is_processing = False


def run_pipeline_sync():
    """Run pipeline synchronously (for background thread)."""
    global pipeline, is_processing
    try:
        is_processing = True
        logger.info("Background processing started")
        count = pipeline.run_all()
        logger.info(f"Background processing complete: {count} file(s)")
        return count
    except Exception as e:
        logger.error(f"Background processing error: {e}", exc_info=True)
        return 0
    finally:
        is_processing = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize pipeline on startup."""
    global pipeline
    
    # Import here to avoid issues during module load
    from run_pipeline import AudioPipeline
    from src.config import Config
    
    try:
        Config.validate()
        pipeline = AudioPipeline()
        logger.info("Pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        raise
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Jarvis Audio Pipeline",
    description="Process voice memos from Google Drive",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"status": "Jarvis Audio Pipeline is running"}


@app.get("/health")
async def health_check():
    """Health check for Cloud Run."""
    return {
        "status": "healthy",
        "processing": is_processing
    }


@app.post("/process")
async def process_files(background: bool = False):
    """
    Process all available audio files in Google Drive.
    Called by Cloud Scheduler every 5 minutes.
    
    Args:
        background: If True, process asynchronously and return immediately.
                   Recommended for large files (2+ hours).
    """
    global pipeline, is_processing
    
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    if is_processing:
        return {
            "status": "already_processing",
            "message": "Processing already in progress"
        }
    
    try:
        logger.info(f"Processing request received (background={background})")
        
        if background:
            # Run in background thread - return immediately
            loop = asyncio.get_event_loop()
            loop.run_in_executor(executor, run_pipeline_sync)
            
            return {
                "status": "accepted",
                "message": "Processing started in background",
                "background": True
            }
        else:
            # Synchronous processing (for short files)
            processed_count = pipeline.run_all()
            
            logger.info(f"Processed {processed_count} file(s)")
            
            return {
                "status": "success",
                "files_processed": processed_count,
                "message": f"Processed {processed_count} file(s)"
            }
        
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process/once")
async def process_one_file():
    """
    Process a single audio file (if available).
    Useful for testing.
    """
    global pipeline
    
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    try:
        success = pipeline.run_once()
        
        return {
            "status": "success" if success else "no_files",
            "processed": success,
            "message": "Processed 1 file" if success else "No files to process"
        }
        
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/drive")
async def drive_webhook(
    request: Request,
    x_goog_channel_id: Optional[str] = Header(None),
    x_goog_resource_state: Optional[str] = Header(None),
    x_goog_resource_id: Optional[str] = Header(None),
    x_goog_message_number: Optional[str] = Header(None)
):
    """
    Webhook endpoint for Google Drive push notifications.
    Triggered when a new file is added to the monitored folder.
    
    IMPORTANT: Returns immediately and processes in background.
    This prevents timeout issues with Google's webhook (10-30s timeout).
    
    Google Drive sends notifications with headers:
    - X-Goog-Channel-ID: The channel ID we specified when creating the watch
    - X-Goog-Resource-State: 'add', 'update', 'remove', 'trash', 'untrash', 'change'
    - X-Goog-Resource-ID: Google's resource identifier
    - X-Goog-Message-Number: Incremental message number
    """
    global pipeline, is_processing
    
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    # Log the notification
    logger.info(f"Drive webhook received: state={x_goog_resource_state}, channel={x_goog_channel_id}, msg={x_goog_message_number}")
    
    # Only process on 'add' or 'change' events (new file uploaded)
    # Note: Google Drive sends 'sync' on initial webhook setup - ignore it
    if x_goog_resource_state not in ['add', 'change']:
        logger.info(f"Ignoring resource state: {x_goog_resource_state}")
        return {"status": "ignored", "reason": f"state={x_goog_resource_state}"}
    
    # Skip if already processing
    if is_processing:
        logger.info("Already processing, skipping webhook trigger")
        return {"status": "skipped", "reason": "already_processing"}
    
    try:
        # Process in background - return immediately to Google
        # This prevents webhook timeout (Google expects response in 10-30s)
        loop = asyncio.get_event_loop()
        loop.run_in_executor(executor, run_pipeline_sync)
        
        logger.info("Webhook accepted, processing in background")
        
        return {
            "status": "accepted",
            "trigger": "webhook",
            "resource_state": x_goog_resource_state,
            "message": "Processing started in background"
        }
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Get current processing status."""
    return {
        "status": "processing" if is_processing else "idle",
        "processing": is_processing,
        "pipeline_ready": pipeline is not None
    }


@app.post("/renew-webhook")
async def renew_webhook_handler():
    import json
    from datetime import datetime, timedelta
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from googleapiclient.discovery import build
    
    try:
        logger.info("Renewing Google Drive webhook...")
        
        # Load credentials
        token_json = os.getenv('GOOGLE_TOKEN_JSON')
        if not token_json:
            raise Exception("GOOGLE_TOKEN_JSON not set")
        
        token_data = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(token_data)
        
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        
        # Build Drive API client
        service = build('drive', 'v3', credentials=creds)
        
        # Get folder ID
        folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID', '').strip()
        if not folder_id:
            raise Exception("GOOGLE_DRIVE_FOLDER_ID not set")
        
        # Get service URL
        service_url = os.getenv('K_SERVICE', 'jarvis-audio-pipeline')
        webhook_url = f"https://{service_url}-776871804948.asia-southeast1.run.app/webhook/drive"
        
        # Create watch with 7-day expiration
        expiration_time = datetime.utcnow() + timedelta(days=7)
        expiration_ms = int(expiration_time.timestamp() * 1000)
        
        body = {
            'id': 'jarvis-audio-pipeline-webhook',
            'type': 'web_hook',
            'address': webhook_url,
            'expiration': expiration_ms
        }
        
        # Stop existing watch (may fail if already expired)
        try:
            service.channels().stop(
                body={'id': 'jarvis-audio-pipeline-webhook', 'resourceId': 'placeholder'}
            ).execute()
            logger.info("Stopped existing watch")
        except Exception:
            pass  # OK if no existing watch
        
        # Create new watch
        response = service.files().watch(
            fileId=folder_id,
            body=body,
            supportsAllDrives=True
        ).execute()
        
        exp_timestamp = int(response.get('expiration', 0)) / 1000
        exp_datetime = datetime.fromtimestamp(exp_timestamp) if exp_timestamp > 0 else None
        
        logger.info(f"Webhook renewed! Expires: {exp_datetime}")
        
        return {
            "status": "success",
            "message": "Webhook renewed",
            "resource_id": response.get('resourceId'),
            "expiration": str(exp_datetime) if exp_datetime else None
        }
        
    except Exception as e:
        logger.error(f"Webhook renewal error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
