"""
Cloud Run HTTP wrapper for Jarvis Audio Pipeline.
Exposes the pipeline as an HTTP API - triggered by Cloud Scheduler.
Uses min-instances=0 for cost efficiency.
"""

import os
import logging
import hmac
import hashlib
from fastapi import FastAPI, HTTPException, Request, Header
from contextlib import asynccontextmanager
from typing import Optional

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
    return {"status": "healthy"}


@app.post("/process")
async def process_files():
    """
    Process all available audio files in Google Drive.
    Called by Cloud Scheduler every 5 minutes.
    """
    global pipeline
    
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    try:
        logger.info("Processing request received")
        
        # Process all available files
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
    
    Google Drive sends notifications with headers:
    - X-Goog-Channel-ID: The channel ID we specified when creating the watch
    - X-Goog-Resource-State: 'add', 'update', 'remove', 'trash', 'untrash', 'change'
    - X-Goog-Resource-ID: Google's resource identifier
    - X-Goog-Message-Number: Incremental message number
    """
    global pipeline
    
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    # Log the notification
    logger.info(f"Drive webhook received: state={x_goog_resource_state}, channel={x_goog_channel_id}, msg={x_goog_message_number}")
    
    # Only process on 'add' or 'change' events (new file uploaded)
    # Note: Google Drive sends 'sync' on initial webhook setup - ignore it
    if x_goog_resource_state not in ['add', 'change']:
        logger.info(f"Ignoring resource state: {x_goog_resource_state}")
        return {"status": "ignored", "reason": f"state={x_goog_resource_state}"}
    
    try:
        # Process all files (webhook tells us something changed, but not specifically what)
        # In future, could optimize to only process files modified after last check
        logger.info("Processing files triggered by webhook")
        processed_count = pipeline.run_all()
        
        logger.info(f"Webhook processing complete: {processed_count} file(s)")
        
        return {
            "status": "success",
            "files_processed": processed_count,
            "trigger": "webhook",
            "resource_state": x_goog_resource_state
        }
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
