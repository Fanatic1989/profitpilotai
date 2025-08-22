#!/usr/bin/env python3
# main.py — FastAPI backend for ProfitPilotAI React SPA (FULL)

from __future__ import annotations

import os, json, asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import jwt

from supabase_utils import (
    init_supabase,
    authenticate_user,
    create_user,
    update_user,
    delete_user,
    list_users,
    get_user_by_login_id,
    get_strategy_configs,
    upsert_strategy_config,
    fetch_pairs_sample,
    save_ai_policy,
    load_ai_policy,
    log_trade,
)

# -------------------------
# Environment & globals
# -------------------------
load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALG = "HS256"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]

supabase = init_supabase(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="ProfitPilotAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Models
# -------------------------
class LoginBody(BaseModel):
    login_id: str
    password: str

class RegisterBody(BaseModel):
    login_id: str
    password: str
    deriv_api_token: Optional[str] = ""
    account_type: Optional[str] = "basic"

class UpdateUserBody(BaseModel):
    login_id: str
    password: Optional[str] = None
    deriv_api_token: Optional[str] = None
    preferred_strategy: Optional[str] = None
    is_active: Optional[bool] = None
    max_trade_amount: Optional[float] = None

class StrategyBody(BaseModel):
    strategy_name: str
    base_amount: float = 1
    multiplier: float = 2
    max_steps: int = 5
    active: bool = True

class SettingsBody(BaseModel):
    deriv_api_token: Optional[str] = None
    account_mode: Optional[str] = "demo"  # "demo" or "real"
    strategy: Optional[str] = "scalping"
    trading_type: Optional[str] = "forex"
    selected_pairs: Optional[List[str]] = []

# -------------------------
# Auth helpers
# -------------------------
def create_access_token(payload: Dict[str, Any], hours: int = 12) -> str:
    to_enc = payload.copy()
    to_enc["exp"] = datetime.utcnow() + timedelta(hours=hours)
    return jwt.encode(to_enc, JWT_SECRET, algorithm=JWT_ALG)

def get_current_user(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid token")
    token = auth.split(" ", 1)[1]
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return data
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

# -------------------------
# Health (incl. HEAD for UptimeRobot)
# -------------------------
@app.head("/health")
@app.get("/health")
async def health():
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}

# -------------------------
# Basic index (for sanity check)
# -------------------------
@app.get("/")
async def root():
    return {"app": "ProfitPilotAI API", "status": "running"}

# -------------------------
# Auth routes
# -------------------------
@app.post("/auth/register")
async def register(body: RegisterBody):
    try:
        user = create_user(
            supabase,
            login_id=body.login_id,
            password=body.password,
            deriv_api_token=body.deriv_api_token or "",
            account_type=body.account_type or "basic",
        )
        return {"ok": True, "user": {"login_id": user["login_id"]}}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/auth/login")
async def login(body: LoginBody):
    user = authenticate_user(supabase, body.login_id, body.password)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token({"login_id": user["login_id"]})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/auth/me")
async def me(current=Depends(get_current_user)):
    login_id = current["login_id"]
    user = get_user_by_login_id(supabase, login_id)
    if not user:
        raise HTTPException(404, "User not found")
    # Do not leak password hash
    user.pop("password", None)
    return {"user": user}

# -------------------------
# Admin routes (protect with JWT; you can add roles later)
# -------------------------
@app.get("/admin/users")
async def admin_list_users(current=Depends(get_current_user)):
    users = list_users(supabase)
    return {"users": users}

class AdminCreateUser(BaseModel):
    login_id: str
    password: str
    deriv_api_token: Optional[str] = ""
    account_type: Optional[str] = "basic"

@app.post("/admin/users")
async def admin_create_user(body: AdminCreateUser, current=Depends(get_current_user)):
    try:
        u = create_user(supabase, body.login_id, body.password, body.deriv_api_token, body.account_type)
        return {"ok": True, "user": {"login_id": u["login_id"]}}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.put("/admin/users/{login_id}")
async def admin_update_user(login_id: str, body: UpdateUserBody, current=Depends(get_current_user)):
    updates = {k: v for k, v in body.dict().items() if v is not None and k != "login_id"}
    try:
        updated = update_user(supabase, login_id, updates)
        updated.pop("password", None)
        return {"ok": True, "user": updated}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.delete("/admin/users/{login_id}")
async def admin_delete_user(login_id: str, current=Depends(get_current_user)):
    try:
        delete_user(supabase, login_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))

# -------------------------
# User settings & bot controls
# -------------------------
@app.get("/pairs")
async def get_pairs(current=Depends(get_current_user)):
    return {"pairs": fetch_pairs_sample()}

@app.post("/user/settings")
async def save_settings(body: SettingsBody, current=Depends(get_current_user)):
    login_id = current["login_id"]
    updates: Dict[str, Any] = {}
    if body.deriv_api_token is not None:
        updates["deriv_api_token"] = body.deriv_api_token
    if body.strategy is not None:
        updates["preferred_strategy"] = body.strategy
    if body.account_mode is not None:
        updates["account_type"] = body.account_mode  # storing simple mode tag
    if body.trading_type is not None:
        updates["trading_type"] = body.trading_type
    if body.selected_pairs is not None:
        updates["selected_pairs"] = body.selected_pairs
    if not updates:
        return {"ok": True}
    updated = update_user(supabase, login_id, updates)
    updated.pop("password", None)
    return {"ok": True, "user": updated}

# Simulated bot state (in-memory) — replace with your runner
BOT_STATE: Dict[str, Dict[str, Any]] = {}  # login_id -> {status, last_event}

@app.post("/bot/start")
async def bot_start(current=Depends(get_current_user)):
    login_id = current["login_id"]
    BOT_STATE[login_id] = {"status": "active", "last_event": datetime.utcnow().isoformat()}
    return {"ok": True, "status": BOT_STATE[login_id]["status"]}

@app.post("/bot/pause")
async def bot_pause(current=Depends(get_current_user)):
    login_id = current["login_id"]
    if login_id not in BOT_STATE:
        BOT_STATE[login_id] = {}
    BOT_STATE[login_id]["status"] = "paused"
    BOT_STATE[login_id]["last_event"] = datetime.utcnow().isoformat()
    return {"ok": True, "status": "paused"}

@app.post("/bot/stop")
async def bot_stop(current=Depends(get_current_user)):
    login_id = current["login_id"]
    BOT_STATE[login_id] = {"status": "inactive", "last_event": datetime.utcnow().isoformat()}
    return {"ok": True, "status": "inactive"}

# -------------------------
# Strategy config endpoints
# -------------------------
@app.get("/strategy/configs")
async def get_configs(current=Depends(get_current_user)):
    login_id = current["login_id"]
    return {"configs": get_strategy_configs(supabase, login_id)}

@app.post("/strategy/configs")
async def add_config(body: StrategyBody, current=Depends(get_current_user)):
    login_id = current["login_id"]
    cfg = upsert_strategy_config(supabase, login_id, body.dict())
    return {"ok": True, "config": cfg}

# -------------------------
# WebSocket — status stream
# -------------------------
clients: Dict[str, List[WebSocket]] = {}

@app.websocket("/ws/{login_id}")
async def ws_status(websocket: WebSocket, login_id: str):
    await websocket.accept()
    clients.setdefault(login_id, []).append(websocket)
    try:
        while True:
            await asyncio.sleep(5)
            state = BOT_STATE.get(login_id, {"status": "inactive"})
            await websocket.send_json({
                "type": "status",
                "login_id": login_id,
                "status": state.get("status", "inactive"),
                "ts": datetime.utcnow().isoformat()
            })
    except WebSocketDisconnect:
        pass
    finally:
        clients[login_id].remove(websocket)

# -------------------------
# Error handler
# -------------------------
@app.exception_handler(Exception)
async def global_err(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})
