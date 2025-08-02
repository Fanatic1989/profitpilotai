import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

# Load environment variables from .env
load_dotenv()

app = FastAPI()

# Middleware for session handling
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "supersecret"))

# Serve static files like style.css and logo.png from root
app.mount("/static", StaticFiles(directory="."), name="static")

templates = Jinja2Templates(directory=".")

# Environment variables
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK")
DISCORD_LINK = os.getenv("DISCORD_LINK")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")           # Default fallback
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # Default fallback

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK
    })

# UptimeRobot HEAD request support
@app.head("/")
async def head_root():
    return Response(status_code=200)

@app.post("/submit", response_class=HTMLResponse)
async def submit(
    request: Request,
    bot_token: str = Form(...),
    login_id: str = Form(...),
    strategy: str = Form(...),
    password: str = Form(...)
):
    if password != ADMIN_PASSWORD:
        return HTMLResponse("<h2>Access Denied ❌ - Invalid Password</h2>", status_code=401)

    print("Received bot config:")
    print(f"Token: {bot_token}")
    print(f"Login ID: {login_id}")
    print(f"Strategy: {strategy}")

    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK,
        "message": "✅ Bot configuration submitted successfully."
    })

# === Admin Panel Section ===

@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin", response_class=HTMLResponse)
async def admin_auth(request: Request, login_id: str = Form(...), password: str = Form(...)):
    print(f"Received login credentials: login_id={login_id}, password={password}")
    print(f"Expected credentials: ADMIN_LOGIN={ADMIN_LOGIN}, ADMIN_PASSWORD={ADMIN_PASSWORD}")
    if login_id == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        print("Login successful")
        return templates.TemplateResponse("admin.html", {"request": request})
    print("Login failed")
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "error": "Invalid login credentials. Please try again."
    })
