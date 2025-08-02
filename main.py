import os
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

# Import additional modules for authentication and database
from auth import verify_user, get_user_dashboard
from models import init_db

# Load environment variables
load_dotenv()

app = FastAPI()

# Middleware for session handling
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "supersecret"))

# Serve static files like style.css and logo.png from root
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize templates and database
templates = Jinja2Templates(directory="templates")
init_db()

# Environment variables
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK")
DISCORD_LINK = os.getenv("DISCORD_LINK")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")           # Default fallback
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # Default fallback

# === Home Page ===
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

    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK,
        "message": "✅ Bot configuration submitted successfully."
    })

# === Admin Panel Section ===
@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.post("/admin", response_class=HTMLResponse)
async def admin_auth(
    request: Request,
    login_id: str = Form(...),
    password: str = Form(...),
    remember_me: str = Form(None)  # Optional "Remember Me" checkbox
):
    if verify_user(login_id, password):  # Use the imported verify_user function
        print("Login successful")
        request.session["admin_logged_in"] = True
        if remember_me == "on":
            pass  # Optional: Add persistent session logic here
        return templates.TemplateResponse("dashboard.html", {"request": request})
    print("Login failed")
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "error": "Invalid login credentials. Please try again."
    })

# === User Dashboard ===
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/", status_code=303)
    trades = get_user_dashboard(user)  # Use the imported get_user_dashboard function
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "trades": trades})

# === Logout ===
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
