"""
Jarvis Audio Pipeline - Cloud Run HTTP Wrapper
Exposes the pipeline as an HTTP API for Cloud Run + Cloud Scheduler.
"""

import os
import logging
import tempfile
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('Jarvis.API')

# Reduce noise
logging.getLogger('httpx').setLevel(logging.WARNING)

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


@app.post("/process/upload")
async def process_uploaded_file(
    file: UploadFile = File(...),
    username: str = Form(default="unknown")
):
    """
    Process an uploaded audio file directly (no Google Drive).
    Returns detailed results about what was created.
    
    Used by Telegram bot for instant processing with feedback.
    """
    global pipeline
    
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")
    
    try:
        logger.info(f"Direct upload received: {file.filename} from {username}")
        
        # Save uploaded file to temp directory
        temp_dir = Path(Config.TEMP_AUDIO_DIR)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        temp_path = temp_dir / file.filename
        
        # Write file to disk
        content = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"Saved to temp: {temp_path} ({len(content)} bytes)")
        
        # Create fake file metadata (as if from Google Drive)
        file_metadata = {
            'id': f'direct_upload_{file.filename}',
            'name': file.filename,
            'mimeType': file.content_type or 'audio/ogg',
            'size': len(content),
            'modifiedTime': None,
            'parents': []
        }
        
        # Process the file directly
        result = pipeline.process_file_direct(file_metadata, temp_path)
        
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
        
        if result.get('success'):
            # Build a human-readable summary
            analysis = result.get('analysis', {})
            category = analysis.get('primary_category', 'recording')
            
            summary_parts = []
            
            # Describe what was created
            meetings = analysis.get('meetings', [])
            reflections = analysis.get('reflections', [])
            tasks = analysis.get('tasks', [])
            
            if meetings:
                for m in meetings:
                    title = m.get('title', 'Untitled')
                    person = m.get('person_name', '')
                    if person:
                        summary_parts.append(f"📅 Meeting: {title} with {person}")
                    else:
                        summary_parts.append(f"📅 Meeting: {title}")
            
            if reflections:
                for r in reflections:
                    title = r.get('title', 'Untitled')
                    summary_parts.append(f"💭 Reflection: {title}")
            
            if tasks:
                for t in tasks:
                    title = t.get('title', 'Untitled')
                    due = t.get('due_context') or t.get('due_date') or ''
                    if due:
                        summary_parts.append(f"✅ Task: {title} (due: {due})")
                    else:
                        summary_parts.append(f"✅ Task: {title}")
            
            # Add CRM contact linking feedback (from db_records merged into analysis)
            contact_matches = analysis.get('contact_matches', [])
            contact_feedback = []
            
            for match in contact_matches:
                searched_name = match.get('searched_name', '')
                
                if match.get('matched') and match.get('linked_contact'):
                    linked = match['linked_contact']
                    linked_name = linked.get('name', searched_name)
                    company = linked.get('company', '')
                    if company:
                        contact_feedback.append(f"👤 Linked to: {linked_name} ({company})")
                    else:
                        contact_feedback.append(f"👤 Linked to: {linked_name}")
                elif match.get('suggestions'):
                    # No exact match but have suggestions
                    suggestions = match['suggestions']
                    suggestion_names = [s.get('name', '') for s in suggestions[:3]]
                    contact_feedback.append(
                        f"⚠️ '{searched_name}' not found. Did you mean: {', '.join(suggestion_names)}?"
                    )
                else:
                    # No match and no suggestions
                    contact_feedback.append(f"➕ Unknown contact: {searched_name}")
            
            if contact_feedback:
                summary_parts.append("")  # Empty line separator
                summary_parts.extend(contact_feedback)
            
            # If nothing was extracted, show generic message
            if not meetings and not reflections and not tasks:
                summary_parts = [f"📝 Recorded as: {category}"]
            
            return {
                "status": "success",
                "category": category,
                "summary": "\n".join(summary_parts),
                "details": {
                    "meetings_created": len(meetings),
                    "reflections_created": len(reflections),
                    "tasks_created": len(tasks),
                    "transcript_id": result.get('transcript_id'),
                    "transcript_length": result.get('transcript_length', 0),
                    "contact_matches": contact_matches,  # Include full details for bot
                    "meeting_ids": analysis.get('meeting_ids', []),  # For linking contacts
                    "reflection_ids": analysis.get('reflection_ids', [])
                }
            }
        else:
            return {
                "status": "error",
                "error": result.get('error', 'Unknown error'),
                "summary": "Failed to process audio"
            }
        
    except Exception as e:
        logger.error(f"Direct upload processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
