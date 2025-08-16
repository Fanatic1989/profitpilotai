import os
import asyncio
import json
from typing import List, Optional
from urllib.parse import unquote

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from supabase import create_client
from apscheduler.schedulers.background import BackgroundScheduler
from bot.engine import run_bot, ExchangeClient  # Updated import path
import requests  # Added to resolve "name 'requests' is not defined" error

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
    raise RuntimeError("SUPABASE_URL and/or SUPABASE_KEY environment variables are not set")

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

# Map user-friendly pairs to Deriv API symbols
DERIV_SYMBOL_MAP = {
    "AUD/USD": "frxAUDUSD",
    "EUR/USD": "frxEURUSD",
    "GBP/USD": "frxGBPUSD",
    "USD/JPY": "frxUSDJPY",
    "USD/CHF": "frxUSDCHF",
    "USD/CAD": "frxUSDCAD",
    "AUD/JPY": "frxAUDJPY",
    "EUR/GBP": "frxEURGBP",
    "EUR/JPY": "frxEURJPY",
    "Volatility 10 Index": "volatility_10_index",
    "Volatility 25 Index": "volatility_25_index",
    "Volatility 50 Index": "volatility_50_index",
    "Volatility 75 Index": "volatility_75_index",
    "Volatility 100 Index": "volatility_100_index",
    "Crash 1000 Index": "crash_1000_index",
    "Crash 500 Index": "crash_500_index",
    "Boom 1000 Index": "boom_1000_index",
    "Boom 500 Index": "boom_500_index"
}

def all_pairs_flat() -> List[str]:
    return [item for group in DERIV_PAIRS for item in group["items"]]

def serialize_pairs(pairs: List[str]) -> List[str]:
    """Returns a Python list of unique, stripped strings from the input."""
    if not pairs:
        return []
    return sorted(set(str(p).strip() for p in pairs if p.strip()))

def deserialize_pairs(raw) -> List[str]:
    """Accepts JSON string, Python list, or comma-separated string and returns a Python list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
            if isinstance(val, list):
                return [str(x) for x in val]
        except Exception:
            pass
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []

def _norm_strategy(v: str) -> str:
    v = v.strip().lower()
    mappings = {
        "scalping": "scalping",
        "day trading": "day trading",
        "swing trading": "swing trading"
    }
    return mappings.get(v, v)

def _norm_type(v: str) -> str:
    v = v.strip().lower()
    mappings = {
        "forex": "forex",
        "binary": "binary"
    }
    return mappings.get(v, v)

def _get_username_from_cookie(request: Request) -> Optional[str]:
    return request.cookies.get("username")

# Fetch Deriv trading pairs (defensive networking)
async def get_deriv_pairs() -> List[str]:
    uri = "wss://ws.derivws.com/websockets/v3?app_id=1089"
    try:
        async with websockets.connect(uri, ping_interval=None, close_timeout=5) as ws:
            await ws.send(json.dumps({"active_symbols": "brief", "product_type": "basic"}))
            for _ in range(5):
                response = await asyncio.wait_for(ws.recv(), timeout=8)
                data = json.loads(response)
                if "active_symbols" in data:
                    symbols = []
                    for s in data["active_symbols"]:
                        name = s.get("display_name") or s.get("symbol")
                        if name:
                            symbols.append(name)
                    return sorted(set(symbols))
    except Exception as e:
        print(f"WebSocket error fetching pairs: {e}")
    return []  # fallback to static list

# Helper function to map user-friendly pairs to Deriv API symbols
def map_to_deriv_symbols(pairs: List[str]) -> List[str]:
    return [DERIV_SYMBOL_MAP.get(pair, pair) for pair in pairs]

# --------------------------
# Routes
# --------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    res = supabase.table("user_settings").select("*").eq("login_id", username).execute()
    if not res.data or not pwd_context.verify(password, res.data[0]["password"]):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        }, status_code=401)

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
    username = _get_username_from_cookie(request)
    if not username:
        return RedirectResponse("/", status_code=302)

    res = supabase.table("user_settings").select("*").eq("login_id", username).execute()
    if not res.data:
        return RedirectResponse("/", status_code=302)

    user = res.data[0]
    user.setdefault("total_trades", 0)
    user.setdefault("total_wins", 0)
    user.setdefault("total_losses", 0)
    user.setdefault("total_draws", 0)

    selected_pairs = deserialize_pairs(user.get("selected_pairs"))
    deriv_pairs = await get_deriv_pairs() or all_pairs_flat()

    return templates.TemplateResponse("user_dashboard.html", {
        "request": request,
        "user": user,
        "pairs": DERIV_PAIRS,
        "deriv_pairs": deriv_pairs,
        "selected_pairs": selected_pairs
    })

@app.post("/update-settings")
async def update_settings(
    request: Request,
    trading_type: str = Form(...),
    strategy: str = Form(...),
    risk_percent: int = Form(...),
    pairs: Optional[List[str]] = Form(None),
    password: Optional[str] = Form(None),
):
    username = _get_username_from_cookie(request)
    if not username:
        return RedirectResponse("/", status_code=302)

    ttype = _norm_type(trading_type)
    strat = _norm_strategy(strategy)
    rp = max(1, min(5, int(risk_percent) if str(risk_percent).isdigit() else 1))
    normalized_pairs = sorted(set(str(p).strip() for p in pairs or [] if p.strip()))

    payload = {
        "trading_type": ttype,
        "strategy": strat,
        "risk_percent": rp,
        "selected_pairs": normalized_pairs,  # Pass as a Python list
    }

    if password and password.strip():
        payload["password"] = hash_password(password.strip())

    supabase.table("user_settings").update(payload).eq("login_id", username).execute()
    return RedirectResponse("/dashboard", status_code=303)

# --------------------------
# Admin Panel Routes
# --------------------------

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    username = _get_username_from_cookie(request)
    if not username:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Please log in to access the admin dashboard"})
    
    res = supabase.table("user_settings").select("*").execute()
    users = res.data or []

    for u in users:
        trades = u.get("total_trades") or 0
        wins = u.get("total_wins") or 0
        u["win_rate_local"] = round(wins / trades * 100, 2) if trades > 0 else 0.0

    return templates.TemplateResponse("admin.html", {"request": request, "users": users})

@app.post("/admin/add-user")
async def admin_add_user(
    login_id: str = Form(...),
    bot_token: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...),
    password: str = Form(...),
    lifetime: str = Form(None),
    selected_pairs: Optional[List[str]] = Form(None),  # Ensure this is a list
):
    try:
        hashed_password = hash_password(password)
        strat = _norm_strategy(strategy)
        ttype = _norm_type(trading_type)
        rp = max(1, min(5, int(risk_percent) if str(risk_percent).isdigit() else 1))
        pairs_list = sorted(set(str(p).strip() for p in selected_pairs or []))

        supabase.table("user_settings").insert({
            "login_id": login_id,
            "bot_token": bot_token,
            "password": hashed_password,
            "strategy": strat,
            "trading_type": ttype,
            "risk_percent": rp,
            "total_trades": 0,
            "total_wins": 0,
            "total_losses": 0,
            "lifetime": lifetime == "true",
            "bot_status": "inactive",
            "selected_pairs": pairs_list,  # Pass as a Python list
        }).execute()

        return RedirectResponse(url="/admin", status_code=303)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            content={"error": f"Internal Server Error: {str(e)}"},
            status_code=500
        )

@app.post("/admin/update-user/{login_id}")
async def update_user(
    login_id: str,
    bot_token: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...)
):
    strat = _norm_strategy(strategy)
    ttype = _norm_type(trading_type)
    rp = max(1, min(5, int(risk_percent) if str(risk_percent).isdigit() else 1))

    supabase.table("user_settings").update({
        "bot_token": bot_token,
        "strategy": strat,
        "trading_type": ttype,
        "risk_percent": rp
    }).eq("login_id", login_id).execute()

    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/delete-user/{login_id}")
async def delete_user(login_id: str):
    supabase.table("user_settings").delete().eq("login_id", login_id).execute()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/toggle-bot/{login_id}")
async def toggle_bot(login_id: str):
    res = supabase.table("user_settings").select("bot_status").eq("login_id", login_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")
    curr = res.data[0].get("bot_status", "inactive").lower()
    new_status = "active" if curr != "active" else "inactive"
    supabase.table("user_settings").update({"bot_status": new_status}).eq("login_id", login_id).execute()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/toggle-lifetime/{login_id}")
async def toggle_lifetime(login_id: str):
    res = supabase.table("user_settings").select("lifetime").eq("login_id", login_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")
    curr = bool(res.data[0].get("lifetime"))
    supabase.table("user_settings").update({"lifetime": not curr}).eq("login_id", login_id).execute()
    return RedirectResponse("/admin", status_code=303)

# --------------------------
# Price & Bot Control APIs
# --------------------------

@app.get("/price/{symbol}")
async def price(symbol: str):
    try:
        # Map user-friendly symbol to Deriv API symbol
        deriv_symbol = DERIV_SYMBOL_MAP.get(symbol, symbol)
        sym = unquote(deriv_symbol)
        
        # Fetch market data for the mapped symbol
        df = fetch_market_data(symbol=sym)
        price_val = float(df.iloc[-1]["close"])
        
        return {"symbol": sym, "price": price_val}
    except Exception as e:
        return JSONResponse({"error": f"Failed to fetch price: {e}"}, status_code=500)

@app.post("/bot/{action}")
async def bot_control(action: str, request: Request):
    username = _get_username_from_cookie(request)
    if not username:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    valid_actions = {"start": "active", "pause": "paused", "stop": "inactive"}
    if action not in valid_actions:
        return JSONResponse({"error": "Invalid action"}, status_code=400)

    supabase.table("user_settings").update({"bot_status": valid_actions[action]}).eq("login_id", username).execute()
    return {"status": valid_actions[action]}

@app.get("/bot/status")
async def bot_status(request: Request):
    username = _get_username_from_cookie(request)
    if not username:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    res = supabase.table("user_settings").select("bot_status").eq("login_id", username).execute()
    if not res.data:
        return JSONResponse({"error": "User not found"}, status_code=404)
    return {"status": res.data[0].get("bot_status", "inactive")}

# --------------------------
# Trading Logic
# --------------------------

@app.get("/trade/{login_id}")
async def execute_trade(login_id: str):
    res = supabase.table("user_settings").select("*").eq("login_id", login_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")

    user = res.data[0]
    pairs = deserialize_pairs(user.get("selected_pairs"))
    # Map user-friendly pairs to Deriv API symbols
    deriv_pairs = map_to_deriv_symbols(pairs)
    symbol = deriv_pairs[0] if deriv_pairs else user.get("symbol", "BTCUSD")

    try:
        df = fetch_market_data(symbol=symbol)
        signal = compute_signal(df)
        qty = user.get("risk_percent", 1)
        last_close = float(df.iloc[-1]["close"])

        if signal in ["buy", "sell"]:
            place_order(user_id=login_id, side=signal, quantity=qty, price=last_close)
            return {"symbol": symbol, "signal": signal, "price": last_close}
        return {"symbol": symbol, "signal": signal}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trading error: {str(e)}")

# --------------------------
# Scheduler Integration
# --------------------------

# Initialize the scheduler
scheduler = BackgroundScheduler()

# Start the bot runner as a scheduled task
def start_bot_scheduler():
    api_key = os.getenv("EXCHANGE_API_KEY")
    api_secret = os.getenv("EXCHANGE_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("EXCHANGE_API_KEY and/or EXCHANGE_API_SECRET environment variables are not set")

    exchange_client = ExchangeClient(api_key=api_key, api_secret=api_secret)
    scheduler.add_job(run_bot, "interval", minutes=1, args=[supabase, exchange_client])
    scheduler.start()

# Hook into FastAPI's lifecycle events
@app.on_event("startup")
async def startup_event():
    start_bot_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

# --------------------------
# Global Exception Handling
# --------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled exception: {exc}")
    return JSONResponse(
        content={"error": "An unexpected error occurred. Please try again later."},
        status_code=500
    )
