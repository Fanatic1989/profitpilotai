import os, secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any
from passlib.hash import bcrypt
from loguru import logger
from .supabase_utils import get_client, get_user_by_login_or_email

TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "24"))
SITE_BASE = os.getenv("SITE_BASE", "http://localhost:8000")

def hash_pwd(p: str) -> str:
    return bcrypt.hash(p)

def verify_pwd(p: str, h: str) -> bool:
    try:
        return bcrypt.verify(p, h)
    except Exception:
        return False

def create_user(name: str, address: str, login_id: str, email: str, password: str) -> Tuple[bool, str]:
    sb = get_client()
    if not sb: return False, "Supabase not configured"
    try:
        pw = hash_pwd(password)
        token = secrets.token_urlsafe(32)
        exp = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
        resp = sb.table("app_users").insert({
            "name": name,
            "address": address,
            "login_id": login_id,
            "email": email,
            "password_hash": pw,
            "verify_token": token,
            "verify_expires": exp.isoformat(),
        }).execute()
        return True, token
    except Exception as e:
        logger.exception("create_user failed")
        return False, str(e)

def verify_email_token(token: str) -> bool:
    sb = get_client()
    if not sb: return False
    try:
        now = datetime.now(timezone.utc).isoformat()
        u = sb.table("app_users").select("*").eq("verify_token", token).single().execute().data
        if not u or (u.get("verify_expires") and u["verify_expires"] < now):
            return False
        sb.table("app_users").update({"email_verified": True, "verify_token": None, "verify_expires": None}).eq("id", u["id"]).execute()
        return True
    except Exception:
        return False

def start_password_reset(login_or_email: str) -> Optional[str]:
    sb = get_client()
    if not sb: return None
    try:
        u = get_user_by_login_or_email(login_or_email)
        if not u: return None
        token = secrets.token_urlsafe(32)
        exp = (datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()
        sb.table("app_users").update({"reset_token": token, "reset_expires": exp}).eq("id", u["id"]).execute()
        return token
    except Exception:
        return None

def finish_password_reset(token: str, new_password: str) -> bool:
    sb = get_client()
    if not sb: return False
    try:
        now = datetime.now(timezone.utc).isoformat()
        u = sb.table("app_users").select("*").eq("reset_token", token).single().execute().data
        if not u or (u.get("reset_expires") and u["reset_expires"] < now):
            return False
        sb.table("app_users").update({
            "password_hash": hash_pwd(new_password),
            "reset_token": None,
            "reset_expires": None
        }).eq("id", u["id"]).execute()
        return True
    except Exception:
        return False


# --- shims for legacy imports (main.py expects these here) ---
from .supabase_utils import get_user_by_email as _sb_get_user_by_email, set_role_admin as _sb_set_role_admin

def get_user_by_email(email: str):
    return _sb_get_user_by_email(email)

def set_role_admin(email: str) -> bool:
    return _sb_set_role_admin(email)
