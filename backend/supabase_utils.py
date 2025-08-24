import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, List

from supabase import create_client

# -------- Env + client cache --------
_CLIENT = None
_LAST_ERROR: Optional[str] = None

def _env(name: str, *alts: str) -> Optional[str]:
    for k in (name,)+alts:
        v = os.getenv(k)
        if v and isinstance(v, str) and v.strip() and v.strip() not in ("...", "<set-me>", "CHANGE_ME"):
            return v.strip().strip('"').strip("'")
    return None

def get_client():
    """Return cached Supabase client or None (and set _LAST_ERROR) if missing/invalid env."""
    global _CLIENT, _LAST_ERROR
    if _CLIENT is not None:
        return _CLIENT
    url = _env("SUPABASE_URL")
    key = _env("SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY")
    if not url or not key or "supabase.co" not in url or not url.startswith("https://"):
        _LAST_ERROR = "Missing/invalid SUPABASE_URL or KEY"
        return None
    try:
        _CLIENT = create_client(url, key)
        _LAST_ERROR = None
        return _CLIENT
    except Exception as e:
        _LAST_ERROR = str(e)
        return None

# -------- Users --------
def get_user_by_login_or_email(login_or_email: str) -> Optional[Dict[str, Any]]:
    """
    Fetch user by email OR login_id from app_users.
    Returns dict or None.
    """
    sb = get_client()
    if not sb:
        return None
    v = login_or_email.strip()
    try:
        # supabase-py or() filter string
        res = sb.table("app_users").select("*").or_(f"email.eq.{v},login_id.eq.{v}").limit(1).execute()
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None

# -------- Rate limit (login attempts) --------
# Table expected:
# create table if not exists login_attempts (ip text, ts timestamptz default now());
def is_rate_limited(ip: str, max_attempts: int, window_seconds: int) -> bool:
    sb = get_client()
    if not sb:
        return False
    try:
        since = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).isoformat()
        res = sb.table("login_attempts").select("count(*)", count="exact").gte("ts", since).eq("ip", ip).execute()
        # When using count="exact", the count lands on res.count or via content-range; robust fallback:
        count = getattr(res, "count", None)
        if count is None:
            # Some drivers return rows; count(*) as count
            rows = res.data or []
            if rows and isinstance(rows[0], dict):
                count = int(rows[0].get("count", 0))
            else:
                count = 0
        return int(count) >= max_attempts
    except Exception:
        return False

def record_failed_attempt(ip: str) -> None:
    sb = get_client()
    if not sb:
        return
    try:
        sb.table("login_attempts").insert({"ip": ip}).execute()
    except Exception:
        pass

def clear_attempts(ip: str) -> None:
    sb = get_client()
    if not sb:
        return
    try:
        sb.table("login_attempts").delete().eq("ip", ip).execute()
    except Exception:
        pass

# -------- Subscriptions --------
# Table expected:
# create table if not exists subscriptions (
#   id uuid primary key default gen_random_uuid(),
#   user_id uuid not null references app_users(id) on delete cascade,
#   plan text not null default 'custom',
#   status text not null default 'active',
#   current_period_end timestamptz not null,
#   created_at timestamptz not null default now()
# );
def get_user_and_latest_sub(login_or_email: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    sb = get_client()
    if not sb:
        return None, None
    user = get_user_by_login_or_email(login_or_email)
    if not user:
        return None, None
    try:
        res = (
            sb.table("subscriptions")
            .select("*")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        sub = (res.data or [None])[0]
        return user, sub
    except Exception:
        return user, None

def is_subscription_active(sub: Optional[Dict[str, Any]]) -> bool:
    if not sub:
        return False
    end_raw = sub.get("current_period_end")
    if not end_raw:
        return False
    try:
        # Accepts ISO; handle potential 'Z'
        end_dt = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
    except Exception:
        return False
    return end_dt > datetime.now(timezone.utc) and (sub.get("status") in (None, "", "active"))

def grant_user(login_or_email: str, days: int, plan: str = "manual") -> bool:
    """
    Extend user's subscription by `days` from max(now, current end).
    Creates user row if missing? (No: return False to avoid side-effects.)
    """
    sb = get_client()
    if not sb:
        return False
    user = get_user_by_login_or_email(login_or_email)
    if not user:
        return False
    try:
        # fetch latest current_period_end if any
        res = (
            sb.table("subscriptions")
            .select("current_period_end")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        now_ = datetime.now(timezone.utc)
        if res.data:
            raw = res.data[0].get("current_period_end")
            try:
                cur_end = datetime.fromisoformat(str(raw).replace("Z","+00:00"))
            except Exception:
                cur_end = now_
        else:
            cur_end = now_
        new_end = max(now_, cur_end) + timedelta(days=days)
        payload = {
            "user_id": user["id"],
            "plan": plan,
            "status": "active",
            "current_period_end": new_end.isoformat()
        }
        sb.table("subscriptions").insert(payload).execute()
        return True
    except Exception:
        return False

def delete_user(login_or_email: str) -> bool:
    sb = get_client()
    if not sb:
        return False
    user = get_user_by_login_or_email(login_or_email)
    if not user:
        return False
    try:
        # subscriptions on delete cascade will handle if FK set; do explicit just in case
        try:
            sb.table("subscriptions").delete().eq("user_id", user["id"]).execute()
        except Exception:
            pass
        sb.table("app_users").delete().eq("id", user["id"]).execute()
        return True
    except Exception:
        return False

def list_active_users() -> List[Dict[str, Any]]:
    sb = get_client()
    if not sb:
        return []
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        res = sb.table("subscriptions").select("user_id,current_period_end,status").gt("current_period_end", now_iso).eq("status","active").execute()
        active_user_ids = sorted({row["user_id"] for row in (res.data or []) if row.get("user_id")})
        users: List[Dict[str, Any]] = []
        for uid in active_user_ids:
            ures = sb.table("app_users").select("id,name,email,login_id,role,created_at").eq("id", uid).limit(1).execute()
            row = (ures.data or [None])[0]
            if row:
                users.append(row)
        return users
    except Exception:
        return []

# Optional: expose last client error to the debug endpoint
def _last_error() -> Optional[str]:
    return _LAST_ERROR

def get_user_by_email(email: str):
    sb = get_client()
    if not sb:
        return None
    try:
        res = sb.table("app_users").select("*").eq("email", email.strip()).limit(1).execute()
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None

def set_role_admin(email: str) -> bool:
    sb = get_client()
    if not sb:
        return False
    try:
        # ensure user exists
        res = sb.table("app_users").select("id,role").eq("email", email.strip()).limit(1).execute()
        rows = res.data or []
        if not rows:
            return False
        uid = rows[0]["id"]
        sb.table("app_users").update({"role": "admin"}).eq("id", uid).execute()
        return True
    except Exception:
        return False
