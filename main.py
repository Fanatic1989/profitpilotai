import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

# === Home Page ===
@app.get("/", response_class=HTMLResponse)
async def read_root():
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

    # Set session variables
    request.session["user_logged_in"] = True
    request.session["login_id"] = login_id
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
async def admin_login():
    try:
        with open("admin.html", "r") as file:
            content = file.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin.html not found</h1>", status_code=404)

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

        try:
            with open("dashboard.html", "r") as file:
                content = file.read()
            return HTMLResponse(content=content)
        except FileNotFoundError:
            return HTMLResponse("<h1>Error: dashboard.html not found</h1>", status_code=404)

    print("Login failed")
    try:
        with open("admin.html", "r") as file:
            content = file.read()
        return HTMLResponse(content=content.replace("{{ error }}", "Invalid login credentials. Please try again."))
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin.html not found</h1>", status_code=404)

# === User Dashboard ===
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/", status_code=303)

    try:
        with open("dashboard.html", "r") as file:
            content = file.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: dashboard.html not found</h1>", status_code=404)

# === Logout ===
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
