# Speaker Identification - Recognize Specific People

## Current State: Anonymous Speaker Labels

WhisperX currently identifies speakers as:
- **Speaker 1**: Unknown person
- **Speaker 2**: Unknown person
- **Speaker 3**: Unknown person

## Goal: Named Speaker Labels

After enrollment:
- **Aaron**: Your voice
- **Speaker 2**: Unrecognized person
- **Speaker 3**: Unrecognized person

## Implementation Options

### Option 1: Voice Enrollment Database (Recommended)

Create a voice profile for you by recording short audio samples.

**How it works:**
1. Record 3-5 short audio clips of you speaking (30-60 seconds each)
2. Extract voice embeddings from these clips
3. Store embeddings in a database
4. Match new speakers against known embeddings
5. Label matches with your name

**Pros:**
- Most accurate (~95% accuracy)
- Works across different recordings
- Can add multiple people over time

**Cons:**
- Requires initial voice samples
- Small database to maintain

### Option 2: First Speaker = Aaron (Simple)

Assume the first person speaking in each recording is you.

**How it works:**
1. Always label "Speaker 1" as "Aaron"
2. Other speakers remain "Speaker 2", "Speaker 3", etc.

**Pros:**
- No setup required
- Works immediately

**Cons:**
- Only works if you always speak first
- Breaks if someone else starts the recording

### Option 3: Manual Labeling in Notion

Let AI suggest speakers, you confirm identities in Notion.

**How it works:**
1. Transcribe with anonymous labels
2. Claude AI suggests who each speaker might be (based on context)
3. You confirm/edit names in Notion

**Pros:**
- No voice training needed
- Flexible and easy to correct

**Cons:**
- Requires manual confirmation
- AI suggestions may be wrong

## Recommended Implementation: Option 1 + 2 Hybrid

**Workflow:**
1. **Create voice profile**: Record 3-5 samples of you speaking
2. **Auto-match**: System tries to match speakers to your profile
3. **Fallback rule**: If confidence is high (>85%) and you're detected as first speaker, label as "Aaron"
4. **Unknown speakers**: Labeled "Unknown 1", "Unknown 2", etc.
5. **Manual override**: Edit names in Notion if needed

## Implementation Plan

### Step 1: Create Voice Profile (One-Time Setup)

Record yourself speaking in different scenarios:

```python
# scripts/setup/create_voice_profile.py

from src.core.speaker_identifier import VoiceProfileCreator

creator = VoiceProfileCreator()

# Record 3-5 audio samples (or use existing recordings)
samples = [
    "path/to/sample1.mp3",  # You on a call
    "path/to/sample2.mp3",  # You in a meeting
    "path/to/sample3.mp3",  # You doing a voice note
]

# Create profile
creator.create_profile(
    name="Aaron",
    audio_files=samples,
    output="data/voice_profiles/aaron.pkl"
)
```

### Step 2: Update Transcriber to Use Profiles

```python
# src/core/transcriber.py

class WhisperXTranscriber:
    def __init__(self):
        # ... existing code ...
        
        # Load voice profiles
        self.speaker_identifier = SpeakerIdentifier()
        self.speaker_identifier.load_profiles("data/voice_profiles/")
    
    def transcribe(self, audio_path):
        # ... existing transcription code ...
        
        # After diarization, identify known speakers
        if diarize_segments:
            identified_speakers = self.speaker_identifier.identify_speakers(
                audio_path=audio_path,
                diarize_segments=diarize_segments
            )
            
            # Replace "Speaker 1" with "Aaron" if matched
            for segment in segments:
                speaker_id = segment.get('speaker')
                if speaker_id in identified_speakers:
                    segment['speaker'] = identified_speakers[speaker_id]
```

### Step 3: Create Speaker Identifier Module

```python
# src/core/speaker_identifier.py

import pickle
import numpy as np
from resemblyzer import VoiceEncoder
from pathlib import Path

class SpeakerIdentifier:
    """Match anonymous speakers to known voice profiles"""
    
    def __init__(self, confidence_threshold=0.85):
        self.encoder = VoiceEncoder()
        self.profiles = {}
        self.confidence_threshold = confidence_threshold
    
    def load_profiles(self, profiles_dir):
        """Load all voice profiles from directory"""
        for profile_path in Path(profiles_dir).glob("*.pkl"):
            with open(profile_path, 'rb') as f:
                profile = pickle.load(f)
                self.profiles[profile['name']] = profile['embedding']
    
    def identify_speakers(self, audio_path, diarize_segments):
        """
        Match diarized speakers to known profiles
        
        Returns: {"SPEAKER_00": "Aaron", "SPEAKER_01": "Unknown 1"}
        """
        # Extract embeddings for each speaker in this audio
        speaker_embeddings = self._extract_speaker_embeddings(
            audio_path, 
            diarize_segments
        )
        
        # Match each speaker to known profiles
        identified = {}
        unknown_count = 1
        
        for speaker_id, embedding in speaker_embeddings.items():
            best_match, confidence = self._find_best_match(embedding)
            
            if confidence >= self.confidence_threshold:
                identified[speaker_id] = best_match
            else:
                identified[speaker_id] = f"Unknown {unknown_count}"
                unknown_count += 1
        
        return identified
    
    def _find_best_match(self, embedding):
        """Find closest matching profile"""
        if not self.profiles:
            return None, 0.0
        
        similarities = {}
        for name, profile_embedding in self.profiles.items():
            # Cosine similarity
            similarity = np.dot(embedding, profile_embedding) / (
                np.linalg.norm(embedding) * np.linalg.norm(profile_embedding)
            )
            similarities[name] = similarity
        
        best_match = max(similarities, key=similarities.get)
        confidence = similarities[best_match]
        
        return best_match, confidence


class VoiceProfileCreator:
    """Create voice profiles from audio samples"""
    
    def __init__(self):
        self.encoder = VoiceEncoder()
    
    def create_profile(self, name, audio_files, output):
        """Create voice profile from multiple audio samples"""
        embeddings = []
        
        for audio_file in audio_files:
            # Load and preprocess audio
            from resemblyzer import preprocess_wav
            wav = preprocess_wav(audio_file)
            
            # Extract embedding
            embedding = self.encoder.embed_utterance(wav)
            embeddings.append(embedding)
        
        # Average embeddings for robust profile
        avg_embedding = np.mean(embeddings, axis=0)
        
        # Save profile
        profile = {
            'name': name,
            'embedding': avg_embedding,
            'num_samples': len(audio_files)
        }
        
        with open(output, 'wb') as f:
            pickle.dump(profile, f)
        
        print(f"✅ Created voice profile for {name}")
        print(f"   Samples used: {len(audio_files)}")
        print(f"   Saved to: {output}")
```

## Quick Start: Simple Implementation

If you want to start immediately without voice samples:

### Option: "First Speaker = Aaron" Rule

<function_calls>
<invoke name="read_file">
<parameter name="filePath">c:\Users\aaron\My Drive\Jarvis\Jarvis\src\core\transcriber.py