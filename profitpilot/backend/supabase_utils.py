#!/usr/bin/env python3
# supabase_utils.py — Supabase helpers (FULL)

from __future__ import annotations
import os, logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from supabase import create_client, Client
from passlib.hash import pbkdf2_sha256

log = logging.getLogger("profitpilot-supabase")
log.setLevel(logging.INFO)

_supabase: Optional[Client] = None

def init_supabase(url: Optional[str] = None, key: Optional[str] = None) -> Client:
    global _supabase
    if _supabase:
        return _supabase
    url = url or os.getenv("SUPABASE_URL")
    key = key or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be provided")
    _supabase = create_client(url, key)
    return _supabase

def now_iso() -> str:
    return datetime.utcnow().isoformat()

# -------------------------
# User CRUD & auth
# -------------------------
def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        return pbkdf2_sha256.verify(password, hashed)
    except Exception:
        return False

def get_user_by_login_id(client: Client, login_id: str) -> Optional[Dict[str, Any]]:
    resp = client.table("user_settings").select("*").eq("login_id", login_id).maybe_single().execute()
    if getattr(resp, "error", None):
        log.error("get_user_by_login_id error: %s", resp.error)
        return None
    return resp.data

def list_users(client: Client) -> List[Dict[str, Any]]:
    resp = client.table("user_settings").select("id, login_id, preferred_strategy, is_active, created_at").order("created_at", desc=True).execute()
    if getattr(resp, "error", None):
        log.error("list_users error: %s", resp.error)
        return []
    return resp.data or []

def create_user(client: Client, login_id: str, password: str, deriv_api_token: str = "", account_type: str = "basic") -> Dict[str, Any]:
    check = client.table("user_settings").select("login_id").eq("login_id", login_id).maybe_single().execute()
    if getattr(check, "data", None):
        raise ValueError("User already exists")

    payload = {
        "login_id": login_id,
        "password": hash_password(password),
        "bot_token": "",
        "deriv_api_token": deriv_api_token or "",
        "account_type": account_type or "basic",
        "max_trade_amount": 0,
        "preferred_strategy": "martingale",
        "is_active": True,
        "created_at": now_iso(),
    }
    res = client.table("user_settings").insert(payload).execute()
    if getattr(res, "error", None):
        raise RuntimeError(getattr(res.error, "message", "Insert failed"))
    return res.data[0] if getattr(res, "data", None) else payload

def delete_user(client: Client, login_id: str) -> None:
    res = client.table("user_settings").delete().eq("login_id", login_id).execute()
    if getattr(res, "error", None):
        raise RuntimeError("Failed to delete user")

def update_user(client: Client, login_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    if "password" in updates and updates["password"]:
        updates["password"] = hash_password(updates["password"])
    res = client.table("user_settings").update(updates).eq("login_id", login_id).execute()
    if getattr(res, "error", None):
        raise RuntimeError("Failed to update user")
    return (res.data or [{}])[0]

def authenticate_user(client: Client, login_id: str, password: str) -> Optional[Dict[str, Any]]:
    resp = client.table("user_settings").select("*").eq("login_id", login_id).maybe_single().execute()
    user = getattr(resp, "data", None)
    if not user:
        return None
    return user if verify_password(password, user["password"]) else None

# -------------------------
# Strategy config
# -------------------------
def get_strategy_configs(client: Client, login_id: str) -> List[Dict[str, Any]]:
    resp = client.table("strategy_configs").select("*").eq("login_id", login_id).execute()
    if getattr(resp, "error", None):
        log.error("get_strategy_configs error: %s", resp.error)
        return []
    return resp.data or []

def upsert_strategy_config(client: Client, login_id: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "login_id": login_id,
        "strategy_name": cfg.get("strategy_name", "martingale"),
        "base_amount": cfg.get("base_amount", 1),
        "multiplier": cfg.get("multiplier", 2),
        "max_steps": cfg.get("max_steps", 5),
        "active": cfg.get("active", True),
    }
    res = client.table("strategy_configs").insert(payload).execute()
    if getattr(res, "error", None):
        raise RuntimeError("Failed to upsert strategy config")
    return (res.data or [{}])[0]

# -------------------------
# AI state (simple JSON policy)
# -------------------------
def load_ai_policy(client: Client, login_id: str) -> Dict[str, Any]:
    try:
        resp = client.table("user_states").select("state").eq("user_id", login_id).maybe_single().execute()
        if getattr(resp, "data", None):
            return resp.data.get("state", {}) or {}
        return {}
    except Exception as e:
        log.warning("load_ai_policy error: %s", e)
        return {}

def save_ai_policy(client: Client, login_id: str, policy: Dict[str, Any]) -> None:
    try:
        payload = {"user_id": login_id, "state": policy, "updated_at": now_iso()}
        res = client.table("user_states").upsert(payload, on_conflict="user_id").execute()
        if getattr(res, "error", None):
            log.error("save_ai_policy supabase error: %s", res.error)
    except Exception as e:
        log.exception("save_ai_policy error: %s", e)

# -------------------------
# Trade logs
# -------------------------
def log_trade(client: Client, login_id: str, trade_id: str, contract_type: str, stake: float, profit_loss: float, result: str) -> None:
    payload = {
        "login_id": login_id,
        "trade_id": trade_id,
        "contract_type": contract_type,
        "stake": float(stake),
        "profit_loss": float(profit_loss),
        "result": result,
        "created_at": now_iso()
    }
    try:
        res = client.table("trade_logs").insert(payload).execute()
        if getattr(res, "error", None):
            log.error("log_trade supabase error: %s", res.error)
    except Exception as e:
        log.exception("log_trade error: %s", e)

# -------------------------
# Sample pairs
# -------------------------
def fetch_pairs_sample() -> List[Dict[str, str]]:
    return [
        {"symbol": "frxEURUSD", "display_name": "EUR/USD", "market": "forex"},
        {"symbol": "frxUSDJPY", "display_name": "USD/JPY", "market": "forex"},
        {"symbol": "frxGBPUSD", "display_name": "GBP/USD", "market": "forex"},
        {"symbol": "R_25", "display_name": "Volatility 25 Index", "market": "synthetic"},
        {"symbol": "R_100", "display_name": "Volatility 100 Index", "market": "synthetic"},
    ]
