import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from loguru import logger
try:
    from supabase import create_client

# --- httpx shim: accept `proxy=` kwarg and map to `proxies=` (fix gotrue>=2.9 with httpx<0.26) ---
def _patch_httpx_proxy_kw():
    try:
        import httpx as _httpx
        _orig_init = _httpx.Client.__init__
        def _patched_init(self, *args, **kwargs):
            if 'proxy' in kwargs and 'proxies' not in kwargs:
                kwargs['proxies'] = kwargs.pop('proxy')
            return _orig_init(self, *args, **kwargs)
        # idempotent: only patch once
        if getattr(_httpx.Client.__init__, '__name__', '') != '_patched_init':
            _httpx.Client.__init__ = _patched_init
    except Exception:
        pass

except Exception:
    create_client = None



# --- robust env loading ---
def _env(name, *alts):
    for k in (name,)+alts:
        v = os.getenv(k)
        if v and isinstance(v, str) and v.strip() and v.strip() not in ("...", "<set-me>", "CHANGE_ME"):
            return v.strip().strip('"').strip("'")
    return None

_client_cache = None

_last_client_error = None

def get_client():
    global _client_cache, _last_client_error
    if _client_cache:
        return _client_cache
    url = _env("SUPABASE_URL")
    key = _env("SUPABASE_KEY","SUPABASE_SERVICE_ROLE_KEY","SUPABASE_SERVICE_KEY")
    if not url or not key or "supabase.co" not in url or not url.startswith("https://"):
        _last_client_error = "Missing/invalid SUPABASE_URL or KEY"
        return None
    # ensure httpx shim is installed before any client instantiation
    _patch_httpx_proxy_kw()
    try:
        c = create_client(url, key)
        _client_cache = c
        _last_client_error = None
        return c
    except Exception as e:
        _last_client_error = str(e)
        return None
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    sb = get_client()
    if not sb:
        return False
    try:
        return sb.table("app_users").select("*").eq("email", email).single().execute().data
    except Exception:
        return None

def get_user_by_login_or_email(login_or_email: str) -> Optional[Dict[str, Any]]:
    sb = get_client()
    if not sb:
        return False
    try:
        # try login_id
        data = sb.table("app_users").select("*").eq("login_id", login_or_email).single().execute().data
        return data
    except Exception:
        pass
    try:
        data = sb.table("app_users").select("*").eq("email", login_or_email).single().execute().data
        return data
    except Exception:
        return None

def set_role_admin(email: str) -> bool:
    sb = get_client()
    if not sb:
        return False
    try:
        sb.table("app_users").update({"role":"admin"}).eq("email", email).execute()
        return True
    except Exception:
        return False

def get_user_and_latest_sub(email: str) -> Optional[Dict[str, Any]]:
    sb = get_client()
    if not sb:
        return False
    try:
        u = sb.table("app_users").select("id,email,role").eq("email", email).single().execute().data
        subs = sb.table("subscriptions").select("*").eq("user_id", u["id"]).order("created_at", desc=True).limit(1).execute().data
        return {"user": u, "sub": (subs[0] if subs else None)}
    except Exception:
        return None

def is_subscription_active(sub: Optional[Dict[str, Any]]) -> bool:
    if not sub: return False
    if (sub.get("status","").lower() != "active"): return False
    exp = sub.get("current_period_end")
    if not exp: return True  # lifetime
    try:
        dt = datetime.fromisoformat(exp.replace("Z",""))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc)
    except Exception:
        return False

def add_days_from_current_end(user_id: str, days: int) -> Optional[str]:
    """
    Extends the user's subscription by +days from the later of (now, current_period_end).
    Creates or updates a row; returns ISO expiry.
    """
    sb = get_client()
    if not sb:
        return False
    now = datetime.now(timezone.utc)
    try:
        last = sb.table("subscriptions").select("id,current_period_end,status").eq("user_id", user_id)\
                .order("created_at", desc=True).limit(1).execute().data
        if last and last[0].get("current_period_end"):
            cur = datetime.fromisoformat(last[0]["current_period_end"].replace("Z",""))
            if cur.tzinfo is None: cur = cur.replace(tzinfo=timezone.utc)
            base = max(now, cur)
        else:
            base = now
        new_end = base + timedelta(days=days)
        payload = {
            "user_id": user_id,
            "status": "active",
            "stripe_customer_id": None,
            "stripe_subscription_id": None,  # not stripe; you can tag "np_invoice_x" elsewhere if needed
            "current_period_end": new_end.isoformat()
        }
        # if last row exists, update it; else insert new
        if last:
            sb.table("subscriptions").update(payload).eq("id", last[0]["id"]).execute()
        else:
            sb.table("subscriptions").insert(payload).execute()
        return new_end.isoformat()
    except Exception as e:
        logger.exception("add_days_from_current_end failed")
        return None

# ---- RATE LIMIT (persistent) ----
def rate_window_now() -> datetime:
    return datetime.now(timezone.utc)

def is_rate_limited(ip: str, max_attempts: int, window_seconds: int) -> bool:
    sb = get_client()
    if not sb:
        return False
    now = rate_window_now()
    try:
        rec = sb.table("auth_throttle").select("*").eq("ip", ip).single().execute().data
        if not rec: return False
        if rec["window_end"] <= now.isoformat():
            # window expired; treat as not limited
            return False
        return rec["attempts"] >= max_attempts
    except Exception:
        return False

def record_failed_attempt(ip: str, max_attempts: int, window_seconds: int):
    sb = get_client()
    if not sb:
        return False
    now = rate_window_now()
    win_end = now + timedelta(seconds=window_seconds)
    try:
        # upsert logic: if exists and window still valid, inc; else reset
        rec = sb.table("auth_throttle").select("*").eq("ip", ip).single().execute().data
        if rec:
            if rec["window_end"] <= now.isoformat():
                sb.table("auth_throttle").update({"attempts": 1, "window_end": win_end.isoformat()}).eq("ip", ip).execute()
            else:
                sb.table("auth_throttle").update({"attempts": rec["attempts"] + 1}).eq("ip", ip).execute()
        else:
            sb.table("auth_throttle").insert({"ip": ip, "attempts": 1, "window_end": win_end.isoformat()}).execute()
    except Exception:
        # if single() fails (no row), insert new
        sb.table("auth_throttle").upsert({"ip": ip, "attempts": 1, "window_end": win_end.isoformat()}).execute()

def clear_attempts(ip: str):
    sb = get_client()
    if not sb:
        return False
    try:
        sb.table("auth_throttle").delete().eq("ip", ip).execute()
    except Exception:
        pass

# ===== Admin helpers: grant/delete/list users =====
def _find_user_by_identifier(identifier: str):
    """Identifier can be email or login_id."""
    sb = get_client()
    if not sb:
        return False
    u = None
    try:
        u = sb.table("app_users").select("*").eq("email", identifier).single().execute().data
    except Exception:
        pass
    if not u:
        try:
            u = sb.table("app_users").select("*").eq("login_id", identifier).single().execute().data
        except Exception:
            u = None
    return u

def grant_user(identifier: str, plan: str) -> bool:
    """
    plan: one of ['1w','1m','1y','lifetime']
    - 1w => +7 days
    - 1m => +30 days
    - 1y => +365 days
    - lifetime => status active, current_period_end NULL
    """
    sb = get_client()
    if not sb:
        return False
    u = _find_user_by_identifier(identifier)
    if not u: return False
    plan = (plan or '').lower().strip()
    if plan == 'lifetime':
        try:
            # upsert/ensure a row marked active with no expiry
            last = sb.table("subscriptions").select("id").eq("user_id", u["id"]).order("created_at", desc=True).limit(1).execute().data
            payload = {"user_id": u["id"], "status": "active", "provider": "admin", "external_id": None, "current_period_end": None}
            if last:
                sb.table("subscriptions").update(payload).eq("id", last[0]["id"]).execute()
            else:
                sb.table("subscriptions").insert(payload).execute()
            return True
        except Exception:
            return False
    days_map = {'1w':7, '1m':30, '1y':365}
    days = days_map.get(plan)
    if not days: return False
    return add_days_from_current_end(u["id"], days=days) is not None

def delete_user(identifier: str) -> bool:
    """Delete user and cascade (subscriptions table has ON DELETE CASCADE)."""
    sb = get_client()
    if not sb:
        return False
    u = _find_user_by_identifier(identifier)
    if not u: return False
    try:
        sb.table("app_users").delete().eq("id", u["id"]).execute()
        return True
    except Exception:
        return False

def list_active_users():
    """
    Return list of active users with expiry:
    [{email, login_id, status, current_period_end}]
    Active if status='active' and (expiry >= now OR expiry is null for lifetime).
    """
    sb = get_client()
    if not sb:
        return False
    try:
        users = sb.table("app_users").select("id,email,login_id").execute().data or []
        # fetch latest sub per user
        active = []
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for u in users:
            subs = sb.table("subscriptions").select("*").eq("user_id", u["id"]).order("created_at", desc=True).limit(1).execute().data
            sub = subs[0] if subs else None
            if not sub: 
                continue
            if (sub.get("status","").lower() != "active"):
                continue
            exp = sub.get("current_period_end")
            if exp is None:
                active.append({"email": u["email"], "login_id": u.get("login_id"), "status": "active", "current_period_end": None})
            else:
                try:
                    dt = datetime.fromisoformat(exp.replace("Z",""))
                    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                    if dt >= now:
                        active.append({"email": u["email"], "login_id": u.get("login_id"), "status": "active", "current_period_end": exp})
                except Exception:
                    pass
        return active
    except Exception:
        return []

import os
from datetime import datetime, timedelta, timezone
import bcrypt
from supabase import create_client



# --- robust env loading ---
def _env(name, *alts):
    for k in (name,)+alts:
        v = os.getenv(k)
        if v and isinstance(v, str) and v.strip() and v.strip() not in ("...", "<set-me>", "CHANGE_ME"):
            return v.strip().strip('"').strip("'")
    return None

_client_cache = None

_last_client_error = None

def get_client():
    global _client_cache, _last_client_error
    if _client_cache:
        return _client_cache
    url = _env("SUPABASE_URL")
    key = _env("SUPABASE_KEY","SUPABASE_SERVICE_ROLE_KEY","SUPABASE_SERVICE_KEY")
    if not url or not key or "supabase.co" not in url or not url.startswith("https://"):
        _last_client_error = "Missing/invalid SUPABASE_URL or KEY"
        return None
    # ensure httpx shim is installed before any client instantiation
    _patch_httpx_proxy_kw()
    try:
        c = create_client(url, key)
        _client_cache = c
        _last_client_error = None
        return c
    except Exception as e:
        _last_client_error = str(e)
        return None
def hash_pwd(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_pwd(hashv: str, password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashv.encode())
    except Exception:
        return False



def create_user(name: str, address: str, login_id: str, email: str, password: str, role: str = "user"):
    sb = get_client();  
    if not sb: return None
    if get_user_by_email(email) or (login_id and get_user_by_login_id(login_id)):
        return None
    try:
        ph = hash_pwd(password)
        row = {"name": name, "address": address, "login_id": login_id, "email": email, "password_hash": ph, "role": role}
        return sb.table("app_users").insert(row).execute().data[0]
    except Exception:
        return None



import secrets
def _now_utc(): return datetime.now(timezone.utc)

def save_verify_token(user_id: str, ttl_minutes: int = 60*24) -> str:
    sb = get_client();  
    if not sb: return ""
    tok = secrets.token_urlsafe(32)
    try:
        sb.table("app_users").update({"verify_token": tok, "verify_expires": _now_utc()+timedelta(minutes=ttl_minutes)}).eq("id", user_id).execute()
        return tok
    except Exception:
        return ""

def verify_email_token(token: str) -> bool:
    sb = get_client();  
    if not sb: return False
    try:
        data = sb.table("app_users").select("id,verify_expires").eq("verify_token", token).single().execute().data
        if not data: return False
        exp = data.get("verify_expires")
        if exp and datetime.fromisoformat(str(exp).replace("Z","")).replace(tzinfo=timezone.utc) < _now_utc():
            return False
        sb.table("app_users").update({"email_verified": True, "verify_token": None, "verify_expires": None}).eq("id", data["id"]).execute()
        return True
    except Exception:
        return False



def save_reset_token(email: str, ttl_minutes: int = 30) -> str:
    sb = get_client();  
    if not sb: return ""
    user = get_user_by_email(email)
    if not user: return ""
    tok = secrets.token_urlsafe(32)
    try:
        sb.table("app_users").update({"reset_token": tok, "reset_expires": _now_utc()+timedelta(minutes=ttl_minutes)}).eq("id", user["id"]).execute()
        return tok
    except Exception:
        return ""

def get_user_by_reset_token(token: str):
    sb = get_client();  
    if not sb: return None
    try:
        u = sb.table("app_users").select("*").eq("reset_token", token).single().execute().data
        if not u: return None
        exp = u.get("reset_expires")
        if exp and datetime.fromisoformat(str(exp).replace("Z","")).replace(tzinfo=timezone.utc) < _now_utc():
            return None
        return u
    except Exception:
        return None

def update_password(user_id: str, new_password: str) -> bool:
    sb = get_client();  
    if not sb: return False
    try:
        ph = hash_pwd(new_password)
        sb.table("app_users").update({"password_hash": ph, "reset_token": None, "reset_expires": None}).eq("id", user_id).execute()
        return True
    except Exception:
        return False

