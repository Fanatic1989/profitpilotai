import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# App setup
app = FastAPI()

# Middleware for session handling
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "supersecret"))

# Serve static files (e.g., style.css, logo.png) from the /static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Environment variables
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK")
DISCORD_LINK = os.getenv("DISCORD_LINK")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")           # Default fallback
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # Default fallback

# Simulated in-memory storage for user submissions
user_submissions = []

# === Home Page ===
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        with open("index.html", "r") as file:
            content = file.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: index.html not found</h1>", status_code=404)

# UptimeRobot HEAD request support
@app.head("/")
async def head_root():
    return Response(status_code=200)  # Respond to HEAD requests with a 200 OK status

# === Bot Configuration Submission ===
@app.post("/submit", response_class=HTMLResponse)
async def submit(
    request: Request,
    bot_token: str = Form(...),
    login_id: str = Form(...),
    strategy: str = Form(...),
    password: str = Form(...),
    remember_me: str = Form(None)  # Optional "Remember Me" checkbox
):
    if password != ADMIN_PASSWORD:
        return HTMLResponse("<h2>Access Denied ❌ - Invalid Password</h2>", status_code=401)

    print("Received bot config:")
    print(f"Token: {bot_token}")
    print(f"Login ID: {login_id}")
    print(f"Strategy: {strategy}")

    # Save user submission to session
    request.session["user"] = {
        "bot_token": bot_token,
        "login_id": login_id,
        "strategy": strategy
    }

    # Save to in-memory log for admin view
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

    if remember_me == "on":
        pass  # Optional: Add persistent session logic here

    try:
        with open("index.html", "r") as file:
            content = file.read()
        return HTMLResponse(content=content.replace("{{ message }}", "✅ Bot configuration submitted successfully."))
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: index.html not found</h1>", status_code=404)

# === Admin Panel Section ===
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
    password: str = Form(...),
    remember_me: str = Form(None)  # Optional "Remember Me" checkbox
):
    if login_id == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        print("Login successful")
        request.session["admin_logged_in"] = True
        if remember_me == "on":
            pass  # Optional: Add persistent session logic here

        return RedirectResponse("/admin/dashboard", status_code=303)

    print("Login failed")
    try:
        with open("admin_login.html", "r") as file:
            content = file.read()
        return HTMLResponse(content=content.replace("{{ error }}", "Invalid login credentials. Please try again."))
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin_login.html not found</h1>", status_code=404)

# === Admin Dashboard ===
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

    # Find logs for this user
    logs = []
    for entry in user_submissions:
        if entry["login_id"] == user_data["login_id"]:
            logs = entry["trade_logs"]
            break

    try:
        with open("user_dashboard.html", "r") as file:
            content = file.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: user_dashboard.html not found</h1>", status_code=404)

# === Logout ===
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
