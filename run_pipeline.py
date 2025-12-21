#!/usr/bin/env python3
"""
Jarvis Audio Processing Pipeline - Simple Runner
Replaces Airflow with a single Python script.

Usage:
    python run_pipeline.py              # Process all new files
    python run_pipeline.py --once       # Process one file and exit
    python run_pipeline.py --daemon     # Run continuously (every 15 min)
    
Environment Variables Required:
    SUPABASE_URL, SUPABASE_KEY
    GOOGLE_DRIVE_FOLDER_ID, GOOGLE_DRIVE_PROCESSED_FOLDER_ID
"""

import os
import sys
import time
import uuid
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.supabase.multi_db import SupabaseMultiDatabase
from src.tasks import (
    monitor_google_drive,
    download_audio_file,
    transcribe_audio,
    analyze_transcript_multi,
    move_to_processed,
    cleanup_temp_files
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('Jarvis.Pipeline')

# Reduce noise from libraries
logging.getLogger('httpx').setLevel(logging.WARNING)


class AudioPipeline:
    """Simple audio processing pipeline - no Airflow required."""
    
    def __init__(self):
        self.db = SupabaseMultiDatabase()
        self.processed_files = set()
        logger.info("Audio pipeline initialized")
    
    def process_file(self, file_metadata: dict) -> bool:
        """
        Process a single audio file through the entire pipeline.
        
        Returns True if successful, False otherwise.
        """
        run_id = str(uuid.uuid4())
        file_name = file_metadata.get('name', 'unknown')
        start_time = time.time()
        
        logger.info(f"{'='*60}")
        logger.info(f"Processing: {file_name}")
        logger.info(f"Run ID: {run_id}")
        logger.info(f"{'='*60}")
        
        # Log pipeline start
        self.db.log_pipeline_event(
            run_id=run_id,
            event_type='pipeline_start',
            status='started',
            message=f'Starting pipeline for {file_name}',
            source_file=file_name
        )
        
        # Context passed between tasks (replaces Airflow XCom)
        context = {
            'run_id': run_id,
            'task_results': {
                'monitor_google_drive': {
                    'file_found': True,
                    'file_metadata': file_metadata
                }
            }
        }
        
        try:
            # Step 1: Download
            step_start = time.time()
            logger.info("Step 1/5: Downloading audio...")
            download_result = download_audio_file(context)
            context['task_results']['download_audio_file'] = download_result
            
            self.db.log_pipeline_event(
                run_id=run_id,
                event_type='download',
                status='success',
                message=f"Downloaded: {download_result.get('file_name')}",
                source_file=file_name,
                duration_ms=int((time.time() - step_start) * 1000)
            )
            logger.info(f"  ✓ Downloaded: {download_result.get('local_path')}")
            
            # Step 2: Transcribe
            step_start = time.time()
            logger.info("Step 2/5: Transcribing audio...")
            transcribe_result = transcribe_audio(context)
            context['task_results']['transcribe_audio'] = transcribe_result
            
            self.db.log_pipeline_event(
                run_id=run_id,
                event_type='transcribe',
                status='success',
                message=f"Transcribed: {transcribe_result.get('duration', 0):.0f}s audio → {len(transcribe_result.get('text', ''))} chars",
                source_file=file_name,
                duration_ms=int((time.time() - step_start) * 1000)
            )
            logger.info(f"  ✓ Transcribed: {len(transcribe_result.get('text', ''))} characters")
            
            # Step 3: Analyze
            step_start = time.time()
            logger.info("Step 3/5: Saving & Analyzing with Intelligence Service...")
            analyze_result = analyze_transcript_multi(context)
            context['task_results']['analyze_transcript_multi'] = analyze_result
            
            self.db.log_pipeline_event(
                run_id=run_id,
                event_type='analyze',
                status='success',
                message=f"Category: {analyze_result.get('primary_category')}, Meetings: {len(analyze_result.get('meetings', []))}, Reflections: {len(analyze_result.get('reflections', []))}",
                source_file=file_name,
                duration_ms=int((time.time() - step_start) * 1000)
            )
            logger.info(f"  ✓ Category: {analyze_result.get('primary_category')}")
            logger.info(f"  ✓ Saved: {len(analyze_result.get('meeting_ids', []))} meetings, {len(analyze_result.get('reflection_ids', []))} reflections")
            
            # Step 4: Move to processed folder & cleanup
            logger.info("Cleaning up...")
            move_to_processed(context)
            cleanup_temp_files(context)
            logger.info("  ✓ Moved to processed folder")
            
            # Log success
            total_time = time.time() - start_time
            self.db.log_pipeline_event(
                run_id=run_id,
                event_type='pipeline_complete',
                status='success',
                message=f'Pipeline completed in {total_time:.1f}s',
                source_file=file_name,
                duration_ms=int(total_time * 1000),
                details={
                    'transcript_id': analyze_result.get('transcript_id'),
                    'meeting_ids': analyze_result.get('meeting_ids', []),
                    'reflection_ids': analyze_result.get('reflection_ids', []),
                    'task_ids': analyze_result.get('task_ids', [])
                }
            )
            
            logger.info(f"{'='*60}")
            logger.info(f"✓ COMPLETE in {total_time:.1f}s")
            logger.info(f"{'='*60}")
            
            return True
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            
            self.db.log_pipeline_event(
                run_id=run_id,
                event_type='pipeline_error',
                status='error',
                message=str(e),
                source_file=file_name
            )
            
            # Try to cleanup even on error
            try:
                cleanup_temp_files(context)
            except:
                pass
            
            return False
    
    def process_file_direct(self, file_metadata: dict, local_path) -> dict:
        """
        Process a file that's already downloaded (direct upload, no Google Drive).
        Returns detailed results for API response.
        
        Args:
            file_metadata: Dict with file info (name, mimeType, size, etc.)
            local_path: Path to the local audio file
        
        Returns:
            Dict with success status, analysis results, and any errors
        """
        from pathlib import Path
        run_id = str(uuid.uuid4())
        file_name = file_metadata.get('name', 'unknown')
        start_time = time.time()
        
        logger.info(f"{'='*60}")
        logger.info(f"Processing (direct): {file_name}")
        logger.info(f"Run ID: {run_id}")
        logger.info(f"{'='*60}")
        
        # Log pipeline start
        self.db.log_pipeline_event(
            run_id=run_id,
            event_type='pipeline_start',
            status='started',
            message=f'Starting direct pipeline for {file_name}',
            source_file=file_name
        )
        
        # Context with pre-downloaded file
        context = {
            'run_id': run_id,
            'task_results': {
                'monitor_google_drive': {
                    'file_found': True,
                    'file_metadata': file_metadata
                },
                'download_audio_file': {
                    'audio_path': str(local_path),  # Must be 'audio_path' to match what transcribe_audio expects
                    'file_name': file_name,
                    'file_size': file_metadata.get('size', 0)
                }
            }
        }
        
        try:
            # Step 1: Transcribe (skip download - file already local)
            step_start = time.time()
            logger.info("Step 1/3: Transcribing audio...")
            transcribe_result = transcribe_audio(context)
            context['task_results']['transcribe_audio'] = transcribe_result
            
            self.db.log_pipeline_event(
                run_id=run_id,
                event_type='transcribe',
                status='success',
                message=f"Transcribed: {transcribe_result.get('duration', 0):.0f}s audio → {len(transcribe_result.get('text', ''))} chars",
                source_file=file_name,
                duration_ms=int((time.time() - step_start) * 1000)
            )
            logger.info(f"  ✓ Transcribed: {len(transcribe_result.get('text', ''))} characters")
            
            # Step 2: Analyze
            step_start = time.time()
            logger.info("Step 2/3: Saving & Analyzing with Intelligence Service...")
            analyze_result = analyze_transcript_multi(context)
            context['task_results']['analyze_transcript_multi'] = analyze_result
            
            self.db.log_pipeline_event(
                run_id=run_id,
                event_type='analyze',
                status='success',
                message=f"Category: {analyze_result.get('primary_category')}, Meetings: {len(analyze_result.get('meetings', []))}, Reflections: {len(analyze_result.get('reflections', []))}",
                source_file=file_name,
                duration_ms=int((time.time() - step_start) * 1000)
            )
            logger.info(f"  ✓ Category: {analyze_result.get('primary_category')}")
            logger.info(f"  ✓ Saved: {len(analyze_result.get('meeting_ids', []))} meetings, {len(analyze_result.get('reflection_ids', []))} reflections")
            
            # Step 3: Cleanup (no move needed - wasn't in Google Drive)
            logger.info("Step 3/3: Cleaning up...")
            cleanup_temp_files(context)
            logger.info("  ✓ Cleanup complete")
            
            # Log success
            total_time = time.time() - start_time
            self.db.log_pipeline_event(
                run_id=run_id,
                event_type='pipeline_complete',
                status='success',
                message=f'Direct pipeline completed in {total_time:.1f}s',
                source_file=file_name,
                duration_ms=int(total_time * 1000),
                details={
                    'transcript_id': analyze_result.get('transcript_id'),
                    'meeting_ids': analyze_result.get('meeting_ids', []),
                    'reflection_ids': analyze_result.get('reflection_ids', []),
                    'task_ids': analyze_result.get('task_ids', [])
                }
            )
            
            logger.info(f"{'='*60}")
            logger.info(f"✓ COMPLETE in {total_time:.1f}s")
            logger.info(f"{'='*60}")
            
            return {
                'success': True,
                'transcript_id': analyze_result.get('transcript_id'),
                'transcript_length': len(transcribe_result.get('text', '')),
                'analysis': analyze_result,
                'processing_time': total_time
            }
            
        except Exception as e:
            logger.error(f"Direct pipeline error: {e}", exc_info=True)
            
            self.db.log_pipeline_event(
                run_id=run_id,
                event_type='pipeline_error',
                status='error',
                message=str(e),
                source_file=file_name
            )
            
            # Try to cleanup even on error
            try:
                cleanup_temp_files(context)
            except:
                pass
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_for_files(self) -> list:
        """Check Google Drive for new audio files."""
        context = {
            'processed_file_ids': self.processed_files,
            'in_progress_file_ids': set(),
            'task_results': {}
        }
        
        result = monitor_google_drive(context)
        
        if result.get('file_found'):
            return [result.get('file_metadata')]
        return []
    
    def run_once(self) -> bool:
        """Process one file if available, then exit."""
        files = self.check_for_files()
        
        if not files:
            logger.info("No new files to process")
            return False
        
        file_metadata = files[0]
        file_id = file_metadata.get('id')
        
        success = self.process_file(file_metadata)
        
        if success:
            self.processed_files.add(file_id)
        
        return success
    
    def run_all(self) -> int:
        """Process all available files, return count processed."""
        processed = 0
        
        while True:
            files = self.check_for_files()
            
            if not files:
                break
            
            file_metadata = files[0]
            file_id = file_metadata.get('id')
            
            success = self.process_file(file_metadata)
            
            if success:
                self.processed_files.add(file_id)
                processed += 1
            else:
                # Skip this file on error to prevent infinite loop
                self.processed_files.add(file_id)
        
        return processed
    
    def run_daemon(self, interval_minutes: int = 15):
        """Run continuously, checking for new files every interval."""
        logger.info(f"Starting daemon mode (checking every {interval_minutes} minutes)")
        logger.info("Press Ctrl+C to stop")
        
        while True:
            try:
                processed = self.run_all()
                
                if processed > 0:
                    logger.info(f"Processed {processed} file(s)")
                else:
                    logger.info("No new files")
                
                logger.info(f"Sleeping for {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in daemon loop: {e}")
                time.sleep(60)  # Wait 1 minute on error


def main():
    parser = argparse.ArgumentParser(
        description='Jarvis Audio Processing Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py              # Process all new files and exit
  python run_pipeline.py --once       # Process one file and exit
  python run_pipeline.py --daemon     # Run continuously
  python run_pipeline.py --daemon --interval 5  # Check every 5 minutes
        """
    )
    
    parser.add_argument(
        '--once', 
        action='store_true',
        help='Process only one file then exit'
    )
    parser.add_argument(
        '--daemon', 
        action='store_true',
        help='Run continuously, checking for new files periodically'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=15,
        help='Minutes between checks in daemon mode (default: 15)'
    )
    
    args = parser.parse_args()
    
    # Validate config
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please set required environment variables")
        sys.exit(1)
    
    # Run pipeline
    pipeline = AudioPipeline()
    
    if args.daemon:
        pipeline.run_daemon(interval_minutes=args.interval)
    elif args.once:
        success = pipeline.run_once()
        sys.exit(0 if success else 1)
    else:
        # Default: process all available files
        processed = pipeline.run_all()
        logger.info(f"Done. Processed {processed} file(s).")
        sys.exit(0)


if __name__ == '__main__':
    main()
