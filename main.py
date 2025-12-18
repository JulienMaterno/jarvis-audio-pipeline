"""
Jarvis Audio Pipeline - Cloud Run HTTP Wrapper
Exposes the pipeline as an HTTP API for Cloud Run + Cloud Scheduler.
"""

import os
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('Jarvis.API')

# Reduce noise
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('anthropic').setLevel(logging.WARNING)

# Import pipeline components
from run_pipeline import AudioPipeline
from src.config import Config

# Global pipeline instance
pipeline = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize pipeline on startup."""
    global pipeline
    try:
        Config.validate()
        pipeline = AudioPipeline()
        logger.info("Pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Jarvis Audio Pipeline",
    description="Process voice memos from Google Drive",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "Jarvis Audio Pipeline is running"}


@app.get("/health")
async def health_check():
    """Health check for Cloud Run."""
    return {"status": "healthy"}


@app.post("/process")
async def process_files():
    """
    Process all available audio files in Google Drive.
    Called by Cloud Scheduler.
    """
    global pipeline
    
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    try:
        logger.info("Processing request received")
        
        # Process all available files
        processed_count = pipeline.run_all()
        
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
async def drive_webhook(request: dict = None):
    """
    Google Drive push notification webhook.
    Triggered when files are added/modified in the watched folder.
    Processes files immediately instead of waiting for scheduler.
    """
    global pipeline
    
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    try:
        logger.info("Drive webhook triggered - processing files")
        
        # Process all available files
        processed_count = pipeline.run_all()
        
        return {
            "status": "success",
            "files_processed": processed_count,
            "message": f"Webhook processed {processed_count} file(s)"
        }
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
