import os
import json
import asyncio
import websockets
from typing import List, Optional
from fastapi import FastAPI, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==================== CONFIG ====================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and/or SUPABASE_KEY environment variables are not set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --------------------------
# Fallback & Curated Pairs
# --------------------------

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
    return [item for group in DERIV_PAIRS for item in group["items"]]

def serialize_pairs(pairs: List[str]) -> str:
    try:
        return json.dumps(list(set(pairs)))
    except Exception:
        return "[]"

def deserialize_pairs(raw) -> List[str]:
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

# --------------------------
# WebSocket: Fetch Live Deriv Pairs
# --------------------------
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

# --------------------------
# Auth Helpers
# --------------------------
def get_current_user(request: Request) -> Optional[dict]:
    username = request.cookies.get("username")
    if not username:
        return None
    res = supabase.table("user_settings").select("*").eq("login_id", username).execute()
    return res.data[0] if res.data else None

# --------------------------
# Routes
# --------------------------

@app.head("/")
async def head_check():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, login_id: str = Form(...), password: str = Form(...)):
    res = supabase.table("user_settings").select("*").eq("login_id", login_id).execute()
    if not res.data:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid credentials"
        }, status_code=401)

    user = res.data[0]
    if not pwd_context.verify(password, user["password"]):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid credentials"
        }, status_code=401)

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="username", value=login_id, httponly=True, max_age=60 * 60 * 6)  # 6 hours
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
    deriv_pairs = await get_deriv_pairs()  # live list
    fallback_pairs = all_pairs_flat()     # grouped fallback

    return templates.TemplateResponse("user_dashboard.html", {
        "request": request,
        "user": user,
        "pairs": DERIV_PAIRS,             # for grouped multiselect
        "deriv_pairs": deriv_pairs or fallback_pairs,  # flat list (live or fallback)
        "selected_pairs": selected_pairs
    })

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
        return RedirectResponse("/", status_code=302)

    # Validate and clamp risk
    try:
        risk_percent = int(risk_percent)
        risk_percent = max(1, min(5, risk_percent))
    except (ValueError, TypeError):
        risk_percent = 1

    # Normalize selected pairs
    pairs = pairs or []
    selected_pairs = sorted(set(str(p).strip() for p in pairs if p.strip()))

    # Build update payload
    payload = {
        "trading_type": trading_type.lower(),
        "strategy": strategy.lower(),
        "risk_percent": risk_percent,
        "selected_pairs": serialize_pairs(selected_pairs),
    }

    if new_password and new_password.strip():
        payload["password"] = pwd_context.hash(new_password.strip())

    supabase.table("user_settings").update(payload).eq("login_id", username).execute()
    return RedirectResponse("/dashboard", status_code=303)

# --------------------------
# Admin Panel
# --------------------------

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    username = request.cookies.get("username")
    if not username:
        return RedirectResponse("/")

    # Optional: restrict to specific admin user(s)
    # if username != "admin":
    #     return RedirectResponse("/dashboard")

    res = supabase.table("user_settings").select("*").execute()
    users = res.data or []

    for u in users:
        trades = u.get("total_trades") or 0
        wins = u.get("total_wins") or 0
        u["win_rate"] = round((wins / trades * 100), 2) if trades > 0 else 0.0

    return templates.TemplateResponse("admin.html", {"request": request, "users": users})

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
    try:
        rp = max(1, min(5, int(risk_percent)))
    except Exception:
        rp = 1

    hashed_password = pwd_context.hash(password)
    lifetime_status = lifetime == "true"

    supabase.table("user_settings").insert({
        "login_id": login_id,
        "bot_token": bot_token,
        "password": hashed_password,
        "strategy": strategy.lower(),
        "trading_type": trading_type.lower(),
        "risk_percent": rp,
        "total_trades": 0,
        "total_wins": 0,
        "total_losses": 0,
        "total_draws": 0,
        "lifetime": lifetime_status,
        "bot_status": "inactive",
        "selected_pairs": "[]",
    }).execute()

    return RedirectResponse("/admin", status_code=303)

@app.get("/admin/edit-user/{login_id}", response_class=HTMLResponse)
async def edit_user_form(request: Request, login_id: str):
    res = supabase.table("user_settings").select("*").eq("login_id", login_id).execute()
    if not res.data:
        return RedirectResponse("/admin")
    return templates.TemplateResponse("edit_user.html", {"request": request, "user": res.data[0]})

@app.post("/admin/update-user/{login_id}")
async def update_user(
    login_id: str,
    bot_token: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...)
):
    try:
        rp = max(1, min(5, int(risk_percent)))
    except Exception:
        rp = 1

    supabase.table("user_settings").update({
        "bot_token": bot_token,
        "strategy": strategy.lower(),
        "trading_type": trading_type.lower(),
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
    current = res.data[0]["bot_status"]
    new_status = "active" if current != "active" else "inactive"
    supabase.table("user_settings").update({"bot_status": new_status}).eq("login_id", login_id).execute()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/toggle-lifetime/{login_id}")
async def toggle_lifetime(login_id: str):
    res = supabase.table("user_settings").select("lifetime").eq("login_id", login_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")
    current = res.data[0]["lifetime"]
    supabase.table("user_settings").update({"lifetime": not current}).eq("login_id", login_id).execute()
    return RedirectResponse("/admin", status_code=303)

# --------------------------
# Trading Logic Endpoint
# --------------------------

@app.get("/trade/{login_id}")
async def execute_trade(login_id: str):
    """
    Executes trading logic for a given user.
    """
    res = supabase.table("user_settings").select("*").eq("login_id", login_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")

    user = res.data[0]
    if user.get("bot_status") != "active":
        return {"status": "skipped", "reason": "Bot is not active"}

    # Use first selected pair or fallback
    symbol_list = deserialize_pairs(user.get("selected_pairs"))
    symbol = symbol_list[0] if symbol_list else "BTCUSD"

    try:
        # These functions should be implemented in bot/engine.py
        from bot.engine import fetch_market_data, compute_signal, place_order

        df = fetch_market_data(symbol=symbol)
        signal = compute_signal(df)

        if signal in ["buy", "sell"]:
            price = df.iloc[-1]["close"]
            quantity = user["risk_percent"]  # example usage
            place_order(user_id=login_id, side=signal, quantity=quantity, price=price)

            return {"signal": signal, "symbol": symbol, "price": price}
        else:
            return {"signal": signal, "symbol": symbol}

    except Exception as e:
        return {"error": str(e)}
