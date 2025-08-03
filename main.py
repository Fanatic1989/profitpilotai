import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Middleware for session handling
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "supersecret"))

# Serve static files (e.g., CSS, images) from the /static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Environment variables
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK")
DISCORD_LINK = os.getenv("DISCORD_LINK")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# === On Startup Create Tables ===
@app.on_event("startup")
async def startup():
    # Initialize database or other startup tasks
    pass

# === Home Page ===
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        with open("index.html", "r") as file:  # Read index.html directly from root
            content = file.read()
        return HTMLResponse(content=content.replace("{{ telegram_link }}", TELEGRAM_LINK).replace("{{ discord_link }}", DISCORD_LINK))
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: index.html not found</h1>", status_code=404)

# UptimeRobot HEAD request support
@app.head("/")
async def head_root():
    return Response(status_code=200)  # Respond to HEAD requests with a 200 OK status

# === Submit Bot Config ===
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

    print(f"Received bot config - Token: {bot_token}, Login ID: {login_id}, Strategy: {strategy}")

    try:
        request.session["user"] = {
            "login_id": login_id,
            "bot_token": bot_token,
            "strategy": strategy
        }
        return RedirectResponse("/dashboard", status_code=303)
    except Exception as e:
        return HTMLResponse(f"<h2>Error: {str(e)}</h2>", status_code=500)

# === Admin ===
@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request):
    try:
        with open("admin_login.html", "r") as file:
            content = file.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin_login.html not found</h1>", status_code=404)

@app.post("/admin", response_class=HTMLResponse)
async def admin_auth(
    request: Request,
    login_id: str = Form(...),
    password: str = Form(...)
):
    if login_id == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        request.session["admin_logged_in"] = True
        return RedirectResponse("/admin/dashboard", status_code=303)

    try:
        with open("admin_login.html", "r") as file:
            content = file.read()
        return HTMLResponse(content=content.replace("{{ error }}", "Invalid login credentials. Please try again."))
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin_login.html not found</h1>", status_code=404)

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)

    try:
        with open("admin.html", "r") as file:
            content = file.read()
        return HTMLResponse(content=content)
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

        # Replace placeholders with real session data
        content = content.replace("{{ user.login_id }}", user_data["login_id"])
        content = content.replace("{{ user.bot_token }}", user_data["bot_token"])
        content = content.replace("{{ user.strategy }}", user_data["strategy"])

        # Optional: clean template logic blocks
        content = content.replace("{% if logs %}", "").replace("{% endif %}", "")
        content = content.replace("{% for log in logs %}", "").replace("{% endfor %}", "")
        content = content.replace("{% else %}No trade logs yet.", "")

        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: user_dashboard.html not found</h1>", status_code=404)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
