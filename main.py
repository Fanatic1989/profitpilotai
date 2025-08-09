import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client
from fastapi.templating import Jinja2Templates

# Load .env config
load_dotenv()

# === Supabase Init ===
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === FastAPI App ===
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "supersecret"))
app.mount("/static", StaticFiles(directory="static"), name="static")

# === Template Setup ===
templates = Jinja2Templates(directory="templates")

# === ENV Vars ===
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK")
DISCORD_LINK = os.getenv("DISCORD_LINK")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK or "#",
        "discord_link": DISCORD_LINK or "#"
    })


@app.post("/submit", response_class=HTMLResponse)
async def submit(
    request: Request,
    bot_token: str = Form(...),
    login_id: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...),
    password: str = Form(...),
    lifetime: str = Form(None)
):
    if password != ADMIN_PASSWORD:
        return HTMLResponse("<h2>Access Denied ❌ - Invalid Password</h2>", status_code=401)

    if not (1 <= risk_percent <= 5):
        return HTMLResponse("<h2>Error: Risk % must be between 1 and 5</h2>", status_code=400)

    try:
        supabase.table("user_settings").upsert({
            "login_id": login_id,
            "bot_token": bot_token,
            "strategy": strategy,
            "trading_type": trading_type,
            "risk_percent": risk_percent,
            "total_trades": 0,
            "total_wins": 0,
            "total_losses": 0,
            "bot_status": "active",
            "lifetime": bool(lifetime)
        }).execute()

        if request.session.get("admin_logged_in"):
            return RedirectResponse("/admin/dashboard", status_code=303)

        request.session["user"] = {
            "login_id": login_id,
            "bot_token": bot_token,
            "strategy": strategy,
            "trading_type": trading_type,
            "risk_percent": risk_percent
        }

        return RedirectResponse("/dashboard", status_code=303)

    except Exception as e:
        return HTMLResponse(f"<h2>Server Error: {str(e)}</h2>", status_code=500)


@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": ""})


@app.post("/admin", response_class=HTMLResponse)
async def admin_auth(request: Request, login_id: str = Form(...), password: str = Form(...)):
    if login_id == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        request.session["admin_logged_in"] = True
        return RedirectResponse("/admin/dashboard", status_code=303)
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "error": "Invalid login credentials. Please try again."
    })


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)

    result = supabase.table("user_settings").select("*").execute()
    users = result.data if hasattr(result, 'data') else []
    return templates.TemplateResponse("admin.html", {"request": request, "users": users})


@app.post("/admin/delete-user/{login_id}", response_class=HTMLResponse)
async def delete_user(request: Request, login_id: str):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)
    supabase.table("user_settings").delete().eq("login_id", login_id).execute()
    return RedirectResponse("/admin/dashboard", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_data = request.session.get("user")
    if not user_data:
        return RedirectResponse("/", status_code=303)

    result = supabase.table("user_settings").select("*").eq("login_id", user_data["login_id"]).limit(1).execute()
    if not result.data:
        return HTMLResponse("<h2>No matching user found in database.</h2>", status_code=404)

    row = result.data[0]
    stats = {
        "trading_type": row.get("trading_type", ""),
        "risk_percent": str(row.get("risk_percent", "")),
        "total_trades": row.get("total_trades", 0),
        "total_wins": row.get("total_wins", 0),
        "total_losses": row.get("total_losses", 0),
        "win_rate": row.get("win_rate", 0),
    }

    return templates.TemplateResponse("user_dashboard.html", {
        "request": request,
        "user": user_data,
        "stats": stats
    })


@app.post("/update-settings", response_class=HTMLResponse)
async def update_settings(
    request: Request,
    method: str = Form(...),
    strategy: str = Form(...),
    risk: int = Form(...)
):
    user_data = request.session.get("user")
    if not user_data:
        return RedirectResponse("/", status_code=303)

    supabase.table("user_settings").update({
        "trading_type": method.lower(),
        "strategy": strategy.lower(),
        "risk_percent": risk
    }).eq("login_id", user_data["login_id"]).execute()

    user_data["strategy"] = strategy
    user_data["trading_type"] = method
    user_data["risk_percent"] = risk
    request.session["user"] = user_data

    return RedirectResponse("/dashboard", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# === FIXED: Match HTML Form Actions ===
@app.post("/admin/toggle-lifetime/{login_id}")
async def toggle_lifetime(login_id: str):
    user = supabase.table("user_settings").select("lifetime").eq("login_id", login_id).single().execute().data
    if user:
        supabase.table("user_settings").update({"lifetime": not user["lifetime"]}).eq("login_id", login_id).execute()
    return RedirectResponse("/admin/dashboard", status_code=303)


@app.post("/admin/toggle-bot/{login_id}")
async def toggle_bot(login_id: str):
    user = supabase.table("user_settings").select("bot_status").eq("login_id", login_id).single().execute().data
    if user:
        new_status = "paused" if user["bot_status"] == "active" else "active"
        supabase.table("user_settings").update({"bot_status": new_status}).eq("login_id", login_id).execute()
    return RedirectResponse("/admin/dashboard", status_code=303)
