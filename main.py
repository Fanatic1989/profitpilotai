import os
import asyncio
import json
import websockets
from typing import List, Optional
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from supabase import create_client
from bot.engine import compute_signal, fetch_market_data, place_order

# Initialize FastAPI app
app = FastAPI()

# UptimeRobot HEAD check
@app.head("/")
async def head_check():
    return {"status": "ok"}

# --------------------------
# Supabase config (defensive)
# --------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    # Avoid crashing on import; will fail on first DB use with a clear message instead.
    def _missing_supabase(*args, **kwargs):
        raise RuntimeError("SUPABASE_URL and/or SUPABASE_KEY environment variables are not set")
    supabase = type("MissingSupabase", (), {"table": _missing_supabase})()
else:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --------------------------
# Password hashing
# --------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# --------------------------
# Templates & Static
# --------------------------
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --------------------------
# Helpers / Constants
# --------------------------

# A curated set of Deriv pairs (fallback if WS fetch fails)
DERIV_PAIRS = [
    {"group": "Forex Majors", "items": [
        "AUD/USD", "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD",
        "AUD/JPY", "EUR/GBP", "EUR/JPY", "GBP/JPY", "NZD/USD", "AUD/NZD", "CAD/JPY", "CHF/JPY"
    ]},
    {"group": "Synthetics", "items": [
        "Volatility 10 Index", "Volatility 25 Index", "Volatility 50 Index",
        "Volatility 75 Index", "Volatility 100 Index",
        "Crash 1000 Index", "Crash 500 Index", "Boom 1000 Index", "Boom 500 Index"
    ]},
]

def all_pairs_flat() -> List[str]:
    flat: List[str] = []
    for group in DERIV_PAIRS:
        flat.extend(group["items"])
    return flat

def serialize_pairs(pairs: List[str]) -> str:
    """Store as JSON string for portability."""
    try:
        return json.dumps(pairs)
    except Exception:
        return "[]"

def deserialize_pairs(raw) -> List[str]:
    """Accept JSON string, Python list, or comma-separated string."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        # Try JSON decoding first
        try:
            val = json.loads(raw)
            if isinstance(val, list):
                return [str(x) for x in val]
        except Exception:
            pass
        # Fallback: comma-separated
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []

# Fetch Deriv trading pairs (defensive networking)
async def get_deriv_pairs() -> List[str]:
    uri = "wss://ws.derivws.com/websockets/v3?app_id=1089"
    try:
        async with websockets.connect(uri, ping_interval=None, close_timeout=5) as ws:
            # Request only active symbols (brief) for speed
            await ws.send(json.dumps({"active_symbols": "brief", "product_type": "basic"}))

            # Deriv can send a heartbeat or other messages; loop a few times to find the payload
            for _ in range(5):
                response = await asyncio.wait_for(ws.recv(), timeout=8)
                data = json.loads(response)
                if isinstance(data, dict) and "active_symbols" in data:
                    syms = data.get("active_symbols") or []
                    # Prefer display_name; fallback to symbol
                    out = []
                    for s in syms:
                        name = s.get("display_name") or s.get("symbol")
                        if name:
                            out.append(name)
                    return sorted(set(out))
            return []
    except Exception:
        # Swallow network errors and just return empty list
        return []

# --------------------------
# Routes
# --------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    # If env vars were missing, this will raise with a clear message
    res = supabase.table("user_settings").select("*").eq("login_id", username).execute()

    if not res.data or not pwd_context.verify(password, res.data[0]["password"]):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="username", value=username, httponly=True, max_age=60 * 60 * 6)
    return response

@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("username")
    return resp

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    username = request.cookies.get("username")
    if not username:
        return RedirectResponse(url="/")

    res = supabase.table("user_settings").select("*").eq("login_id", username).execute()
    if not res.data:
        return RedirectResponse(url="/")

    user = res.data[0]

    # Ensure counters exist (avoid template KeyErrors)
    user.setdefault("total_trades", 0)
    user.setdefault("total_wins", 0)
    user.setdefault("total_losses", 0)
    user.setdefault("total_draws", 0)

    # Deserialize selected pairs
    selected_pairs = deserialize_pairs(user.get("selected_pairs"))

    # Try dynamic Deriv pairs; if none, UI can still use the curated fallback
    deriv_pairs = await get_deriv_pairs()

    return templates.TemplateResponse(
        "user_dashboard.html",
        {
            "request": request,
            "user": user,
            "pairs": DERIV_PAIRS,            # grouped fallback list for the grouped multiselect
            "deriv_pairs": deriv_pairs,      # flat list fetched live (can drive a second multiselect)
            "selected_pairs": selected_pairs
        }
    )

@app.post("/update-settings")
async def update_settings(
    request: Request,
    trading_type: str = Form(...),
    strategy: str = Form(...),
    risk_percent: int = Form(...),
    pairs: Optional[List[str]] = Form(None),
    new_password: Optional[str] = Form(None)
):
    username = request.cookies.get("username")
    if not username:
        return RedirectResponse(url="/")

    # Clamp risk_percent defensively between 1 and 5
    try:
        rp = int(risk_percent)
    except Exception:
        rp = 1
    rp = max(1, min(5, rp))

    # Accept whatever pairs came from the UI (may be from live Deriv fetch),
    # but normalize to strings and unique.
    pairs = pairs or []
    normalized_pairs = sorted(set(str(p).strip() for p in pairs if str(p).strip()))

    payload = {
        "trading_type": trading_type,
        "strategy": strategy,
        "risk_percent": rp,
        "selected_pairs": serialize_pairs(normalized_pairs),
    }

    # Optional password change
    if new_password and new_password.strip():
        payload["password"] = hash_password(new_password.strip())

    supabase.table("user_settings").update(payload).eq("login_id", username).execute()

    return RedirectResponse(url="/dashboard", status_code=303)

# --------------------------
# Admin Panel Routes
# --------------------------

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    users = supabase.table("user_settings").select("*").execute()

    # Compute win rate defensively for template
    for u in users.data:
        trades = (u.get("total_trades") or 0)
        wins = (u.get("total_wins") or 0)
        try:
            u["win_rate"] = (wins / trades * 100.0) if trades > 0 else 0.0
        except Exception:
            u["win_rate"] = 0.0
    return templates.TemplateResponse("admin.html", {"request": request, "users": users.data})

@app.post("/admin/add-user")
async def admin_add_user(
    login_id: str = Form(...),
    bot_token: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...),
    password: str = Form(...),
    lifetime: str = Form(None)
):
    hashed_password = hash_password(password)
    lifetime_status = True if lifetime == "true" else False

    # Clamp risk between 1 and 5
    try:
        rp = int(risk_percent)
    except Exception:
        rp = 1
    rp = max(1, min(5, rp))

    supabase.table("user_settings").insert({
        "login_id": login_id,
        "bot_token": bot_token,
        "password": hashed_password,
        "strategy": strategy,
        "trading_type": trading_type,
        "risk_percent": rp,
        "total_trades": 0,
        "total_wins": 0,
        "total_losses": 0,
        "total_draws": 0,
        "lifetime": lifetime_status,
        "bot_status": "inactive",
        "selected_pairs": serialize_pairs([]),
    }).execute()

    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/edit-user/{login_id}", response_class=HTMLResponse)
async def edit_user_form(request: Request, login_id: str):
    res = supabase.table("user_settings").select("*").eq("login_id", login_id).execute()
    if not res.data:
        return RedirectResponse(url="/admin")
    return templates.TemplateResponse("edit_user.html", {"request": request, "user": res.data[0]})

@app.post("/admin/update-user/{login_id}")
async def update_user(
    login_id: str,
    bot_token: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...)
):
    # Clamp risk between 1 and 5
    try:
        rp = int(risk_percent)
    except Exception:
        rp = 1
    rp = max(1, min(5, rp))

    supabase.table("user_settings").update({
        "bot_token": bot_token,
        "strategy": strategy,
        "trading_type": trading_type,
        "risk_percent": rp
    }).eq("login_id", login_id).execute()

    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/delete-user/{login_id}")
async def delete_user(login_id: str):
    supabase.table("user_settings").delete().eq("login_id", login_id).execute()
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/toggle-bot/{login_id}")
async def toggle_bot(login_id: str):
    res = supabase.table("user_settings").select("bot_status").eq("login_id", login_id).execute()
    if not res.data:
        return RedirectResponse(url="/admin", status_code=303)
    curr = (res.data[0].get("bot_status") or "inactive").lower()
    new_status = "active" if curr != "active" else "inactive"
    supabase.table("user_settings").update({"bot_status": new_status}).eq("login_id", login_id).execute()
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/toggle-lifetime/{login_id}")
async def toggle_lifetime(login_id: str):
    res = supabase.table("user_settings").select("lifetime").eq("login_id", login_id).execute()
    if not res.data:
        return RedirectResponse(url="/admin", status_code=303)
    curr = bool(res.data[0].get("lifetime"))
    supabase.table("user_settings").update({"lifetime": not curr}).eq("login_id", login_id).execute()
    return RedirectResponse(url="/admin", status_code=303)

# --------------------------
# Trading Logic
# --------------------------

@app.get("/trade/{login_id}")
async def execute_trade(login_id: str):
    """
    Execute trading logic for a user.
    """
    res = supabase.table("user_settings").select("*").eq("login_id", login_id).execute()
    if not res.data:
        return {"error": "User not found"}

    user = res.data[0]

    # Fetch market data
    symbol = user.get("symbol", "BTCUSD")  # Default to BTCUSD if no symbol is specified
    df = fetch_market_data(symbol=symbol)

    # Compute trading signal
    signal = compute_signal(df)

    # Place order based on signal
    if signal == "buy":
        place_order(user_id=login_id, side="buy", quantity=user["risk_percent"], price=df.iloc[-1]["close"])
    elif signal == "sell":
        place_order(user_id=login_id, side="sell", quantity=user["risk_percent"], price=df.iloc[-1]["close"])

    return {"signal": signal}
