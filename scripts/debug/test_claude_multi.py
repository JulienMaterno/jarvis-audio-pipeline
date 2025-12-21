"""Quick sanity check for the multi-database analysis flow.

This script now calls jarvis-intelligence-service directly instead of using a
local Claude analyzer. Run the intelligence service locally before executing
the script:

    uvicorn main:app --reload
"""

import json
import os
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def test_intelligence_service():
    """POST a sample transcript to the intelligence service analyze endpoint."""

    base_url = os.getenv("INTELLIGENCE_SERVICE_URL", "http://localhost:8000").rstrip("/")
    endpoint = f"{base_url}/api/v1/analyze"

    test_transcript = (
        "Had a great evening reflection today. I've been thinking about my morning routine "
        "and how I can be more productive. I realized I need to start waking up earlier, "
        "maybe around 6am. Also want to start meditating for 10 minutes each morning.\n\n"
        "On another note, I should probably call my mom this weekend, haven't talked to "
        "her in a while. And I need to finish that proposal for the client by Friday."
    )

    payload = {
        "filename": "test_reflection.mp3",
        "transcript": test_transcript,
        "audio_duration_seconds": 180,
        "recording_date": "2025-11-22",
        "language": "en"
    }

    print("\n" + "=" * 60)
    print("TESTING INTELLIGENCE SERVICE ANALYZE ENDPOINT")
    print("=" * 60 + "\n")
    print(f"POST {endpoint}\n")

    try:
        response = requests.post(endpoint, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()
        analysis = data.get("analysis", {})
        db_records = data.get("db_records", {})

        print("✅ SUCCESS! Intelligence service returned a response.\n")
        print("Analysis:")
        print(json.dumps(analysis, indent=2))

        print("\nDatabase Records:")
        print(json.dumps(db_records, indent=2))

        print("\n" + "=" * 60)
        print("BREAKDOWN:")
        print("=" * 60)
        print(f"Primary Category: {analysis.get('primary_category')}")
        print(f"Meetings: {len(analysis.get('meetings', []))}")
        print(f"Journals: {len(analysis.get('journals', []))}")
        print(f"Reflections: {len(analysis.get('reflections', []))}")
        print(f"Tasks: {len(analysis.get('tasks', []))}")
        print(f"CRM Updates: {len(analysis.get('crm_updates', []))}")

    except Exception as exc:  # pragma: no cover - debug helper
        print(f"❌ FAILED: {exc}")
        raise


if __name__ == "__main__":
    test_intelligence_service()
