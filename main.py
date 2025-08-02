import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from fastapi.templating import Jinja2Templates

# Load environment variables from .env
load_dotenv()

# === App Setup ===
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "supersecret"))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory=".")

# === Env Variables ===
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK")
DISCORD_LINK = os.getenv("DISCORD_LINK")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# === Simulated Storage ===
user_submissions = []

# === Home Page ===
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK,
        "message": None
    })

# === Uptime Robot Support ===
@app.head("/")
async def head_root():
    return Response(status_code=200)

# === Bot Configuration Submission ===
@app.post("/submit", response_class=HTMLResponse)
async def submit(
    request: Request,
    bot_token: str = Form(...),
    login_id: str = Form(...),
    strategy: str = Form(...),
    password: str = Form(...),
    remember_me: str = Form(None)
):
    if password != ADMIN_PASSWORD:
        return HTMLResponse("<h2>Access Denied ❌ - Invalid Password</h2>", status_code=401)

    request.session["user"] = {
        "bot_token": bot_token,
        "login_id": login_id,
        "strategy": strategy
    }

    user_submissions.append({
        "bot_token": bot_token,
        "login_id": login_id,
        "strategy": strategy,
        "trade_logs": [
            "Trade 1: BTC +2.3%",
            "Trade 2: ETH -1.1%",
            "Trade 3: SOL +4.2%"
        ]
    })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK,
        "message": "✅ Bot configuration submitted successfully."
    })

# === Admin Login Page ===
@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "error": None
    })

# === Admin Auth Submission ===
@app.post("/admin", response_class=HTMLResponse)
async def admin_auth(
    request: Request,
    login_id: str = Form(...),
    password: str = Form(...),
    remember_me: str = Form(None)
):
    if login_id == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        request.session["admin_logged_in"] = True
        return RedirectResponse("/admin/dashboard", status_code=303)

    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "error": "Invalid login credentials. Please try again."
    })

# === Admin Dashboard ===
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "submissions": user_submissions
    })

# === User Dashboard ===
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_data = request.session.get("user")
    if not user_data:
        return RedirectResponse("/", status_code=303)

    logs = []
    for entry in user_submissions:
        if entry["login_id"] == user_data["login_id"]:
            logs = entry["trade_logs"]
            break

    return templates.TemplateResponse("user_dashboard.html", {
        "request": request,
        "user": user_data,
        "logs": logs
    })

# === Logout ===
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
