"""Supabase module for Jarvis audio pipeline."""

from .client import supabase, get_supabase_client
from .multi_db import SupabaseMultiDatabase

__all__ = ['supabase', 'get_supabase_client', 'SupabaseMultiDatabase']
