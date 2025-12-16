"""
Cloud Run HTTP wrapper for Jarvis Audio Pipeline.
Provides health check endpoint while running pipeline in background.
"""

import os
import threading
import time
import logging
from flask import Flask, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Pipeline state
pipeline_state = {
    'status': 'starting',
    'last_check': None,
    'files_processed': 0,
    'errors': []
}


def run_pipeline_loop():
    """Run the pipeline in a loop (background thread)."""
    global pipeline_state
    
    # Import here to avoid issues during startup
    from run_pipeline import AudioPipeline
    from src.config import Config
    
    try:
        Config.validate()
        pipeline = AudioPipeline()
        pipeline_state['status'] = 'running'
        
        interval_minutes = int(os.getenv('CHECK_INTERVAL_MINUTES', '5'))
        
        while True:
            try:
                logger.info("Checking for new files...")
                pipeline_state['last_check'] = time.strftime('%Y-%m-%d %H:%M:%S')
                
                processed = pipeline.run_all()
                pipeline_state['files_processed'] += processed
                
                if processed > 0:
                    logger.info(f"Processed {processed} file(s)")
                
                logger.info(f"Sleeping for {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"Pipeline error: {e}")
                pipeline_state['errors'].append(str(e))
                if len(pipeline_state['errors']) > 10:
                    pipeline_state['errors'] = pipeline_state['errors'][-10:]
                time.sleep(60)  # Wait 1 minute on error
                
    except Exception as e:
        logger.error(f"Pipeline startup error: {e}")
        pipeline_state['status'] = 'error'
        pipeline_state['errors'].append(str(e))


@app.route('/')
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({
        'status': 'healthy',
        'service': 'jarvis-audio-pipeline',
        'pipeline': pipeline_state
    })


@app.route('/health')
def health_check():
    """Alternative health endpoint."""
    return jsonify({'status': 'ok'})


@app.route('/status')
def status():
    """Detailed status endpoint."""
    return jsonify(pipeline_state)


if __name__ == '__main__':
    # Start pipeline in background thread
    logger.info("Starting pipeline background thread...")
    pipeline_thread = threading.Thread(target=run_pipeline_loop, daemon=True)
    pipeline_thread.start()
    
    # Start Flask server
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting HTTP server on port {port}...")
    app.run(host='0.0.0.0', port=port, threaded=True)
