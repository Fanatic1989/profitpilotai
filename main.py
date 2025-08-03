import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client

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

# === ENV Vars ===
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK")
DISCORD_LINK = os.getenv("DISCORD_LINK")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# === Startup Hook ===
@app.on_event("startup")
async def startup():
    pass  # Placeholder for any init logic

# === Routes ===

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        with open("index.html", "r") as file:
            content = file.read()
        content = content.replace("{{ telegram_link }}", TELEGRAM_LINK or "#")
        content = content.replace("{{ discord_link }}", DISCORD_LINK or "#")
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: index.html not found</h1>", status_code=404)

@app.head("/")
async def head_root():
    return Response(status_code=200)

# === Submit Form to Supabase ===
@app.post("/submit", response_class=HTMLResponse)
async def submit(
    request: Request,
    bot_token: str = Form(...),
    login_id: str = Form(...),
    strategy: str = Form(...),        # scalping / day trading / swing trading
    trading_type: str = Form(...),    # forex / binary
    risk_percent: int = Form(...),    # 1–5 only
    password: str = Form(...)
):
    if password != ADMIN_PASSWORD:
        return HTMLResponse("<h2>Access Denied ❌ - Invalid Password</h2>", status_code=401)

    if not (1 <= risk_percent <= 5):
        return HTMLResponse("<h2>Error: Risk % must be between 1 and 5</h2>", status_code=400)

    try:
        # Save to session
        request.session["user"] = {
            "login_id": login_id,
            "bot_token": bot_token,
            "strategy": strategy,
            "trading_type": trading_type,
            "risk_percent": risk_percent
        }

        # Save to Supabase (upsert ensures uniqueness by login_id)
        response = supabase.table("user_settings").upsert({
            "login_id": login_id,
            "bot_token": bot_token,
            "strategy": strategy,
            "trading_type": trading_type,
            "risk_percent": risk_percent
        }).execute()

        if response.get("error"):
            return HTMLResponse(f"<h2>DB Error: {response['error']['message']}</h2>", status_code=500)

        return RedirectResponse("/dashboard", status_code=303)

    except Exception as e:
        return HTMLResponse(f"<h2>Server Error: {str(e)}</h2>", status_code=500)

# === Admin Login ===
@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request):
    try:
        with open("admin_login.html", "r") as file:
            return HTMLResponse(content=file.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin_login.html not found</h1>", status_code=404)

@app.post("/admin", response_class=HTMLResponse)
async def admin_auth(request: Request, login_id: str = Form(...), password: str = Form(...)):
    if login_id == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        request.session["admin_logged_in"] = True
        return RedirectResponse("/admin/dashboard", status_code=303)

    try:
        with open("admin_login.html", "r") as file:
            return HTMLResponse(content=file.read().replace("{{ error }}", "Invalid login credentials. Please try again."))
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin_login.html not found</h1>", status_code=404)

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)
    try:
        with open("admin.html", "r") as file:
            return HTMLResponse(content=file.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin.html not found</h1>", status_code=404)

# === User Dashboard ===
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_data = request.session.get("user")
    if not user_data:
        return RedirectResponse("/", status_code=303)

    try:
        with open("user_dashboard.html", "r") as file:
            content = file.read()
        content = (
            content.replace("{{ user.login_id }}", user_data["login_id"])
                   .replace("{{ user.bot_token }}", user_data["bot_token"])
                   .replace("{{ user.strategy }}", user_data["strategy"])
                   .replace("{% if logs %}", "")
                   .replace("{% endif %}", "")
                   .replace("{% for log in logs %}", "")
                   .replace("{% endfor %}", "")
                   .replace("{% else %}No trade logs yet.", "")
        )
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: user_dashboard.html not found</h1>", status_code=404)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
