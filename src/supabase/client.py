"""
Supabase client for Jarvis audio pipeline.
Shared connection to Supabase - same as jarvis-backend.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

if not url or not key:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not found in environment variables.")

supabase: Client = create_client(url, key)


def get_supabase_client() -> Client:
    """Get the Supabase client instance."""
    return supabase
