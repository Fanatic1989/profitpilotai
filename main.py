import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response  # Ensure Response is imported
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

# Load environment variables
load_dotenv()

app = FastAPI()

# Middleware for sessions
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "supersecret"))

# Mount static files
app.mount("/static", StaticFiles(directory="."), name="static")

templates = Jinja2Templates(directory=".")

# Environment variables
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK")
DISCORD_LINK = os.getenv("DISCORD_LINK")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # fallback

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK
    })

@app.head("/")
async def head_root():
    return Response(status_code=200)  # Now Response is properly imported

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

# === Admin Panel Routes ===

@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.post("/admin", response_class=HTMLResponse)
async def admin_auth(request: Request, login_id: str = Form(...), password: str = Form(...)):
    if login_id == "admin" and password == ADMIN_PASSWORD:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    return RedirectResponse("/admin", status_code=303)
