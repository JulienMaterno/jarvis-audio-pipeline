"""
Speaker identification using voice embeddings.
Matches anonymous speakers to known voice profiles.
"""

import pickle
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

class SpeakerIdentifier:
    """Match anonymous speakers to known voice profiles using voice embeddings."""
    
    def __init__(self, confidence_threshold: float = 0.75):
        """
        Initialize speaker identifier.
        
        Args:
            confidence_threshold: Minimum similarity score to match a speaker (0-1)
                                 0.75 = balanced, 0.85 = strict, 0.65 = lenient
        """
        self.confidence_threshold = confidence_threshold
        self.profiles = {}
        self.encoder = None
        
        try:
            from resemblyzer import VoiceEncoder
            self.encoder = VoiceEncoder()
            logger.info("✓ Voice encoder loaded for speaker identification")
        except ImportError:
            logger.warning("resemblyzer not installed - speaker identification disabled")
        except Exception as e:
            logger.error(f"Failed to load voice encoder: {e}")
    
    def load_profiles(self, profiles_dir: str) -> int:
        """
        Load voice profiles from directory.
        
        Args:
            profiles_dir: Path to directory containing .pkl profile files
            
        Returns:
            Number of profiles loaded
        """
        profiles_path = Path(profiles_dir)
        if not profiles_path.exists():
            logger.warning(f"Profiles directory not found: {profiles_dir}")
            return 0
        
        loaded = 0
        for profile_path in profiles_path.glob("*.pkl"):
            try:
                with open(profile_path, 'rb') as f:
                    profile = pickle.load(f)
                    name = profile['name']
                    self.profiles[name] = profile['embedding']
                    loaded += 1
                    logger.info(f"✓ Loaded voice profile: {name}")
            except Exception as e:
                logger.error(f"Failed to load profile {profile_path.name}: {e}")
        
        if loaded > 0:
            logger.info(f"✓ Loaded {loaded} voice profile(s)")
        else:
            logger.warning("No voice profiles found - using simple speaker detection")
        
        return loaded
    
    def identify_speakers(
        self, 
        audio_path: str, 
        diarize_segments: List[Dict]
    ) -> Dict[str, str]:
        """
        Match diarized speakers to known voice profiles.
        
        Args:
            audio_path: Path to audio file
            diarize_segments: Segments with speaker labels from WhisperX
            
        Returns:
            Mapping of anonymous IDs to names: {"SPEAKER_00": "Aaron", "SPEAKER_01": "Unknown 1"}
        """
        if not self.encoder or not self.profiles:
            logger.debug("No encoder or profiles available - skipping identification")
            return {}
        
        try:
            # Extract embeddings for each speaker
            speaker_embeddings = self._extract_speaker_embeddings(audio_path, diarize_segments)
            
            # Match each speaker to known profiles
            identified = {}
            unknown_count = 1
            
            for speaker_id, embedding in speaker_embeddings.items():
                best_match, confidence = self._find_best_match(embedding)
                
                if best_match and confidence >= self.confidence_threshold:
                    identified[speaker_id] = best_match
                    logger.info(f"✓ Identified {speaker_id} as {best_match} (confidence: {confidence:.2f})")
                else:
                    identified[speaker_id] = f"Unknown {unknown_count}"
                    unknown_count += 1
                    if best_match:
                        logger.debug(f"Low confidence for {speaker_id}: {best_match} ({confidence:.2f})")
            
            return identified
            
        except Exception as e:
            logger.error(f"Error identifying speakers: {e}", exc_info=True)
            return {}
    
    def _extract_speaker_embeddings(
        self, 
        audio_path: str, 
        diarize_segments: List[Dict]
    ) -> Dict[str, np.ndarray]:
        """
        Extract voice embeddings for each speaker in audio.
        
        Args:
            audio_path: Path to audio file
            diarize_segments: Speaker segments with timestamps
            
        Returns:
            Dict mapping speaker IDs to their average embedding
        """
        from resemblyzer import preprocess_wav
        import librosa
        
        # Load audio
        wav, sr = librosa.load(audio_path, sr=16000)
        
        # Group segments by speaker
        speaker_segments = {}
        for segment in diarize_segments:
            speaker = segment.get('speaker', 'Unknown')
            if speaker == 'Unknown':
                continue
                
            if speaker not in speaker_segments:
                speaker_segments[speaker] = []
            speaker_segments[speaker].append(segment)
        
        # Extract embeddings for each speaker
        speaker_embeddings = {}
        for speaker_id, segments in speaker_segments.items():
            embeddings = []
            
            # Sample up to 5 segments per speaker for efficiency
            sample_segments = segments[:5] if len(segments) > 5 else segments
            
            for segment in sample_segments:
                start_sample = int(segment['start'] * sr)
                end_sample = int(segment['end'] * sr)
                
                # Extract segment audio
                segment_wav = wav[start_sample:end_sample]
                
                # Must be at least 0.5 seconds
                if len(segment_wav) < sr * 0.5:
                    continue
                
                try:
                    # Get embedding for this segment
                    embedding = self.encoder.embed_utterance(segment_wav)
                    embeddings.append(embedding)
                except Exception as e:
                    logger.debug(f"Failed to embed segment: {e}")
                    continue
            
            if embeddings:
                # Average embeddings for robust speaker representation
                avg_embedding = np.mean(embeddings, axis=0)
                speaker_embeddings[speaker_id] = avg_embedding
        
        return speaker_embeddings
    
    def _find_best_match(self, embedding: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Find closest matching profile for embedding.
        
        Args:
            embedding: Voice embedding to match
            
        Returns:
            Tuple of (best_match_name, confidence_score)
        """
        if not self.profiles:
            return None, 0.0
        
        similarities = {}
        for name, profile_embedding in self.profiles.items():
            # Cosine similarity
            similarity = np.dot(embedding, profile_embedding) / (
                np.linalg.norm(embedding) * np.linalg.norm(profile_embedding)
            )
            similarities[name] = float(similarity)
        
        best_match = max(similarities, key=similarities.get)
        confidence = similarities[best_match]
        
        return best_match, confidence


class VoiceProfileCreator:
    """Create voice profiles from audio samples."""
    
    def __init__(self):
        """Initialize profile creator with voice encoder."""
        try:
            from resemblyzer import VoiceEncoder
            self.encoder = VoiceEncoder()
            logger.info("✓ Voice encoder loaded for profile creation")
        except ImportError:
            raise ImportError("resemblyzer not installed. Run: pip install resemblyzer")
    
    def create_profile(
        self, 
        name: str, 
        audio_files: List[str], 
        output_path: str
    ) -> bool:
        """
        Create voice profile from multiple audio samples.
        
        Args:
            name: Speaker name (e.g., "Aaron")
            audio_files: List of paths to audio files with this speaker
            output_path: Where to save the profile (.pkl file)
            
        Returns:
            True if successful
        """
        try:
            import librosa
            
            logger.info(f"Creating voice profile for {name}...")
            logger.info(f"Processing {len(audio_files)} audio file(s)...")
            
            embeddings = []
            
            for i, audio_file in enumerate(audio_files, 1):
                logger.info(f"  [{i}/{len(audio_files)}] Processing {Path(audio_file).name}...")
                
                # Load audio
                wav, sr = librosa.load(audio_file, sr=16000)
                
                # Split into chunks if long (use first 60 seconds)
                max_samples = 60 * sr
                if len(wav) > max_samples:
                    wav = wav[:max_samples]
                
                # Extract embedding
                embedding = self.encoder.embed_utterance(wav)
                embeddings.append(embedding)
                logger.info(f"  ✓ Extracted embedding")
            
            if not embeddings:
                logger.error("No embeddings extracted")
                return False
            
            # Average embeddings for robust profile
            avg_embedding = np.mean(embeddings, axis=0)
            
            # Save profile
            profile = {
                'name': name,
                'embedding': avg_embedding,
                'num_samples': len(audio_files),
                'created': np.datetime64('now')
            }
            
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output, 'wb') as f:
                pickle.dump(profile, f)
            
            logger.info(f"✓ Created voice profile for {name}")
            logger.info(f"  Samples used: {len(audio_files)}")
            logger.info(f"  Saved to: {output}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create profile: {e}", exc_info=True)
            return False
