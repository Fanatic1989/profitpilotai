import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

load_dotenv()

app = FastAPI()

# Middleware for session handling
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "supersecret"))

# Serve static files from current root directory
app.mount("/", StaticFiles(directory=".", html=True), name="static")

templates = Jinja2Templates(directory=".")

# Environment variables
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK")
DISCORD_LINK = os.getenv("DISCORD_LINK")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # default fallback

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK
    })

# This makes HEAD / return 200 OK for UptimeRobot and health checks
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
    # Simple admin-only access
    if password != ADMIN_PASSWORD:
        return HTMLResponse("<h2>Access Denied ❌ - Invalid Password</h2>", status_code=401)

    # Here, you'd securely store this info or use it to configure a bot
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
