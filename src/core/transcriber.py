"""
WhisperX transcriber with speaker diarization support.
Optimized for cloud deployment with GPU acceleration.
"""

import logging
import os
import torch
from pathlib import Path
from typing import Dict, Optional, List

# Import will be available after container rebuild
try:
    from src.core.speaker_identifier import SpeakerIdentifier
    SPEAKER_ID_AVAILABLE = True
except ImportError:
    SPEAKER_ID_AVAILABLE = False

logger = logging.getLogger('Jarvis.Transcriber')


class WhisperXTranscriber:
    """Transcribe audio files using WhisperX with speaker diarization."""
    
    def __init__(self, model_name: str = 'large-v3', enable_diarization: bool = True):
        """Initialize WhisperX model with optional speaker diarization.
        
        Args:
            model_name: Model size (tiny, base, small, medium, large-v2, large-v3)
                       For cloud with GPU: large-v3 (best accuracy, fast with GPU)
                       For local CPU: medium or base
            enable_diarization: Enable speaker diarization (who spoke when)
        """
        import whisperx
        
        self.model_name = model_name
        self.enable_diarization = enable_diarization
        
        # Auto-detect device (GPU in cloud, CPU locally)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if self.device == "cuda" else "int8"
        
        # Set cache directory for model downloads
        cache_dir = os.getenv('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))
        os.makedirs(cache_dir, exist_ok=True)
        
        logger.info(f"Loading WhisperX model: {model_name}")
        logger.info(f"Device: {self.device.upper()} ({compute_type})")
        logger.info(f"Speaker diarization: {'Enabled' if enable_diarization else 'Disabled'}")
        logger.info(f"Cache: {cache_dir}")
        
        # Load WhisperX model
        self.model = whisperx.load_model(
            model_name,
            self.device,
            compute_type=compute_type,
            download_root=cache_dir
        )
        
        # Initialize diarization pipeline if enabled
        self.diarize_model = None
        if enable_diarization:
            try:
                # Get HuggingFace token from environment (needed for diarization)
                hf_token = os.getenv('HUGGINGFACE_TOKEN')
                if hf_token:
                    self.diarize_model = whisperx.DiarizationPipeline(
                        use_auth_token=hf_token,
                        device=self.device
                    )
                    logger.info("✓ Speaker diarization loaded")
                else:
                    logger.warning("HUGGINGFACE_TOKEN not set - diarization disabled")
                    logger.warning("Get token from: https://huggingface.co/settings/tokens")
                    self.enable_diarization = False
            except Exception as e:
                logger.warning(f"Could not load diarization model: {e}")
                self.enable_diarization = False
        
        # Load speaker identifier for voice recognition
        self.speaker_identifier = None
        if SPEAKER_ID_AVAILABLE:
            try:
                self.speaker_identifier = SpeakerIdentifier(confidence_threshold=0.75)
                profiles_loaded = self.speaker_identifier.load_profiles("data/voice_profiles")
                if profiles_loaded > 0:
                    logger.info(f"✓ Voice recognition enabled with {profiles_loaded} profile(s)")
                else:
                    logger.info("Using simple speaker detection (first speaker = Aaron)")
            except Exception as e:
                logger.warning(f"Could not load speaker identifier: {e}")
        
        logger.info("WhisperX model ready")
    
    def transcribe(self, audio_path: Path, language: Optional[str] = None) -> Dict:
        """Transcribe an audio file with speaker diarization.
        
        Args:
            audio_path: Path to audio file
            language: Optional language code (e.g., 'en', 'de'). Auto-detect if None.
        
        Returns:
            Dict with keys:
                - text: Full transcript
                - segments: List of segments with timestamps and speakers
                - language: Detected/specified language
                - duration: Audio duration in seconds
                - speakers: List of unique speakers (if diarization enabled)
        """
        import whisperx
        
        try:
            logger.info(f"Transcribing: {audio_path.name}")
            
            # Load audio
            audio = whisperx.load_audio(str(audio_path))
            
            # Step 1: Transcribe with WhisperX
            logger.info("Step 1/4: Transcribing...")
            result = self.model.transcribe(
                audio,
                batch_size=16 if self.device == "cuda" else 4,
                language=language
            )
            
            detected_language = result.get('language', language or 'en')
            logger.info(f"Language: {detected_language}")
            
            # Step 2: Align whisper output (improves timestamps)
            logger.info("Step 2/4: Aligning timestamps...")
            model_a, metadata = whisperx.load_align_model(
                language_code=detected_language,
                device=self.device
            )
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                self.device,
                return_char_alignments=False
            )
            
            # Step 3: Speaker diarization (if enabled)
            speakers = []
            if self.enable_diarization and self.diarize_model:
                logger.info("Step 3/4: Identifying speakers...")
                diarize_segments = self.diarize_model(audio)
                result = whisperx.assign_word_speakers(diarize_segments, result)
                
                # Extract unique speakers
                speakers = list(set(
                    seg.get('speaker', 'Unknown') 
                    for seg in result["segments"] 
                    if 'speaker' in seg
                ))
                logger.info(f"Found {len(speakers)} speaker(s): {', '.join(speakers)}")
            else:
                logger.info("Step 3/4: Skipping diarization (disabled)")
                diarize_segments = None
            
            # Step 4: Format output
            logger.info("Step 4/4: Formatting output...")
            segments_list = []
            full_text = []
            
            # Try to identify known speakers using voice profiles
            speaker_map = {}
            if diarize_segments and self.speaker_identifier:
                speaker_map = self.speaker_identifier.identify_speakers(
                    str(audio_path), 
                    diarize_segments
                )
            
            # Fallback: Simple rule for unmapped speakers (first speaker = Aaron)
            first_speaker = None
            for segment in result["segments"]:
                speaker = segment.get('speaker', 'Unknown')
                
                if speaker != 'Unknown' and speaker not in speaker_map:
                    if first_speaker is None:
                        # First unmapped speaker is likely Aaron
                        first_speaker = speaker
                        speaker_map[speaker] = "Aaron"
                        logger.info(f"Fallback: Identified {speaker} as Aaron (first speaker)")
                    else:
                        # Other unmapped speakers
                        unknown_num = len([v for v in speaker_map.values() if v.startswith('Unknown')]) + 1
                        speaker_map[speaker] = f"Unknown {unknown_num}"
                
                # Map speaker to friendly name
                friendly_speaker = speaker_map.get(speaker, speaker)
                
                segments_list.append({
                    'start': segment['start'],
                    'end': segment['end'],
                    'text': segment['text'].strip(),
                    'speaker': friendly_speaker
                })
                full_text.append(segment['text'].strip())
            
            duration = segments_list[-1]['end'] if segments_list else 0
            
            transcript_data = {
                'text': ' '.join(full_text),
                'segments': segments_list,
                'language': detected_language,
                'duration': duration,
                'speakers': speakers
            }
            
            logger.info(f"✓ Transcription complete: {duration:.1f}s, {len(segments_list)} segments")
            
            return transcript_data
            
        except Exception as e:
            logger.error(f"Error transcribing {audio_path.name}: {e}", exc_info=True)
            raise
    
    def format_transcript_with_speakers(self, segments: List[Dict]) -> str:
        """Format transcript with timestamps and speaker labels.
        
        Args:
            segments: List of segment dicts with speaker info
        
        Returns:
            Formatted transcript string with speakers and timestamps
        """
        formatted = []
        current_speaker = None
        
        for segment in segments:
            speaker = segment.get('speaker', 'Unknown')
            text = segment['text'].strip()
            start = self._format_timestamp(segment['start'])
            end = self._format_timestamp(segment['end'])
            
            # Add speaker header when speaker changes
            if speaker != current_speaker:
                formatted.append(f"\n[{speaker}]")
                current_speaker = speaker
            
            formatted.append(f"  [{start} - {end}] {text}")
        
        return '\n'.join(formatted)
    
    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Format seconds as MM:SS."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"


# Backward compatibility alias
OptimizedWhisperTranscriber = WhisperXTranscriber
