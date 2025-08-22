"""
backend/supabase_utils.py

Minimal supabase helper utilities using supabase-py.
- Provide client creation and simple functions to insert logs and fetch settings.
- If you don't use Supabase, this module acts as a light wrapper and won't break.
"""

import os
from typing import Dict, Any, Optional

try:
    from supabase import create_client, Client
except Exception:
    # supabase client not installed; provide a stub to avoid hard crashes
    create_client = None
    Client = None

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_client: Optional[Client] = None

def get_supabase_client():
    global _client
    if _client is not None:
        return _client
    if not create_client or not SUPABASE_URL or not SUPABASE_KEY:
        _client = None
        return None
    _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def insert_trade_log(log: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert trade log into 'trade_logs' table. Requires supabase table to exist.
    Returns dict with response or raises.
    """
    client = get_supabase_client()
    if client is None:
        # fallback: just return the log for local use
        return {"status": "noop", "log": log}
    data = client.table("trade_logs").insert(log).execute()
    return data


def fetch_settings(user_id: str) -> Dict[str, Any]:
    client = get_supabase_client()
    if client is None:
        return {}
    resp = client.table("user_settings").select("*").eq("user_id", user_id).execute()
    try:
        return resp.data[0] if resp.data else {}
    except Exception:
        return {}
