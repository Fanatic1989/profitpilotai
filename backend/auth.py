import os
from typing import Optional, Tuple, Dict, Any
from passlib.hash import bcrypt
from loguru import logger
from .supabase_utils import get_client

def hash_pwd(p: str) -> str:
    return bcrypt.hash(p)

def verify_pwd(p: str, h: str) -> bool:
    try:
        return bcrypt.verify(p, h)
    except Exception:
        return False

def create_user(email: str, password: str) -> Tuple[bool, str]:
    sb = get_client()
    if not sb: return False, "Supabase not configured"
    try:
        pw = hash_pwd(password)
        resp = sb.table("app_users").insert({"email": email, "password_hash": pw}).execute()
        return True, resp.data[0]["id"]
    except Exception as e:
        logger.exception("create_user failed")
        return False, str(e)

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    sb = get_client()
    if not sb: return None
    try:
        resp = sb.table("app_users").select("*").eq("email", email).single().execute()
        return resp.data
    except Exception:
        return None

def set_role_admin(email: str) -> bool:
    sb = get_client()
    if not sb: return False
    try:
        sb.table("app_users").update({"role":"admin"}).eq("email", email).execute()
        return True
    except Exception:
        return False
