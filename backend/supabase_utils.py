import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from loguru import logger
try:
    from supabase import create_client
except Exception:
    create_client = None

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_client():
    if not create_client or not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None

# ---- USERS / SUBSCRIPTIONS ----
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
