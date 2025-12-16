#!/usr/bin/env python3
"""
Create a voice profile for speaker identification.

Usage:
    python scripts/setup/create_voice_profile.py

Or specify files directly:
    python scripts/setup/create_voice_profile.py file1.mp3 file2.mp3 file3.mp3
"""

import sys
import logging
from pathlib import Path
from typing import List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.speaker_identifier import VoiceProfileCreator

def get_audio_files_interactive() -> List[str]:
    """Interactively get audio file paths from user."""
    print("📝 Voice Profile Setup for Aaron")
    print("=" * 60)
    print()
    print("To identify your voice in recordings, we need 3-5 audio samples")
    print("of you speaking. These can be:")
    print("  • Voice memos you recorded")
    print("  • Meeting recordings where you spoke")
    print("  • Any audio file with your voice")
    print()
    print("For best results:")
    print("  ✓ Use different recordings (different days, contexts)")
    print("  ✓ Each sample should be 30-60 seconds long")
    print("  ✓ Audio should be clear (minimal background noise)")
    print()
    
    sample_files = []
    print("Enter paths to your audio samples (or press Enter to finish):")
    print()
    
    while len(sample_files) < 5:
        prompt = f"Sample {len(sample_files) + 1} path: "
        path = input(prompt).strip().strip('"').strip("'")
        
        if not path:
            if len(sample_files) >= 3:
                break
            else:
                print(f"⚠️  Need at least 3 samples (you have {len(sample_files)})")
                continue
        
        path_obj = Path(path)
        if not path_obj.exists():
            print(f"❌ File not found: {path}")
            continue
        
        sample_files.append(str(path_obj))
        print(f"✓ Added: {path_obj.name}")
    
    return sample_files

def create_profile(sample_files: List[str], name: str = "Aaron") -> bool:
    """Create voice profile from audio samples."""
    if not sample_files:
        print("❌ No samples provided. Exiting.")
        return False
    
    if len(sample_files) < 3:
        print(f"❌ Need at least 3 samples (you have {len(sample_files)})")
        return False
    
    print()
    print(f"Creating voice profile for {name} from {len(sample_files)} samples...")
    print()
    
    try:
        creator = VoiceProfileCreator()
        
        output_path = f"data/voice_profiles/{name.lower()}.pkl"
        success = creator.create_profile(
            name=name,
            audio_files=sample_files,
            output_path=output_path
        )
        
        if success:
            print()
            print("=" * 60)
            print(f"✅ SUCCESS!")
            print()
            print(f"Voice profile created: {output_path}")
            print()
            print("Next steps:")
            print("  1. Rebuild Docker containers:")
            print("     docker-compose down")
            print("     docker-compose build --no-cache")
            print("     docker-compose up -d")
            print()
            print("  2. Your voice will now be automatically recognized in all recordings!")
            print()
            return True
        else:
            print()
            print("❌ Failed to create voice profile. Check logs above.")
            return False
            
    except ImportError:
        print()
        print("❌ ERROR: resemblyzer not installed")
        print()
        print("Install it with:")
        print("  pip install resemblyzer")
        print()
        print("Then run this script again.")
        return False
    except Exception as e:
        print()
        print(f"❌ ERROR: {e}")
        return False

def scan_voice_samples_folder() -> List[str]:
    """Scan data/voice_samples folder for audio files."""
    samples_dir = Path("data/voice_samples")
    
    if not samples_dir.exists():
        return []
    
    # Common audio extensions
    audio_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.mp4'}
    audio_files = []
    
    for ext in audio_extensions:
        audio_files.extend(samples_dir.glob(f"*{ext}"))
    
    return [str(f.resolve()) for f in sorted(audio_files)]

def main():
    """Main entry point."""
    # Check if files provided as arguments
    if len(sys.argv) > 1:
        sample_files = [str(Path(f).resolve()) for f in sys.argv[1:]]
        # Validate files exist
        valid_files = []
        for f in sample_files:
            if Path(f).exists():
                valid_files.append(f)
                print(f"✓ Found: {Path(f).name}")
            else:
                print(f"⚠️  Not found: {f}")
        
        if valid_files:
            create_profile(valid_files)
        else:
            print("❌ No valid files found")
            sys.exit(1)
    else:
        # Check voice_samples folder first
        sample_files = scan_voice_samples_folder()
        
        if sample_files:
            print("📁 Found audio files in data/voice_samples/:")
            print()
            for i, f in enumerate(sample_files, 1):
                print(f"  {i}. {Path(f).name}")
            print()
            response = input(f"Use these {len(sample_files)} file(s) to create voice profile? (y/n): ").strip().lower()
            
            if response in ['y', 'yes']:
                create_profile(sample_files)
            else:
                # Interactive mode
                sample_files = get_audio_files_interactive()
                if sample_files:
                    create_profile(sample_files)
        else:
            print("📁 No audio files found in data/voice_samples/")
            print()
            print("You can either:")
            print("  1. Move your voice memos to: data/voice_samples/")
            print("  2. Provide file paths interactively")
            print()
            response = input("Enter file paths interactively? (y/n): ").strip().lower()
            
            if response in ['y', 'yes']:
                sample_files = get_audio_files_interactive()
                if sample_files:
                    create_profile(sample_files)

if __name__ == "__main__":
    main()
