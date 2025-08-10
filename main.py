import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
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


@app.on_event("startup")
async def startup():
    pass


# ============================================
# Public Registration Form (GET)
# ============================================
@app.get("/register", response_class=HTMLResponse)
async def register_form():
    html = """
    <h1>Register</h1>
    <form method="post" action="/register">
        <label>Login ID:</label>
        <input type="text" name="login_id" required><br><br>
        <label>Password:</label>
        <input type="password" name="password" required><br><br>
        <label>Bot Token:</label>
        <input type="text" name="bot_token" required><br><br>
        <label>Strategy:</label>
        <select name="strategy">
            <option>scalping</option>
            <option>day trading</option>
            <option>swing trading</option>
        </select><br><br>
        <label>Trading Type:</label>
        <select name="trading_type">
            <option>forex</option>
            <option>binary</option>
        </select><br><br>
        <label>Risk Percent (1-5):</label>
        <input type="number" name="risk_percent" min="1" max="5" required><br><br>
        <button type="submit">Create Account</button>
    </form>
    <p>Already have an account? <a href="/login">Login here</a></p>
    """
    return HTMLResponse(content=html)


# ============================================
# Handle Registration (POST)
# ============================================
@app.post("/register", response_class=HTMLResponse)
async def register_user(
    login_id: str = Form(...),
    password: str = Form(...),
    bot_token: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...)
):
    if not (1 <= risk_percent <= 5):
        return HTMLResponse("<h2>Error: Risk % must be between 1 and 5</h2>", status_code=400)

    existing = supabase.table("user_settings").select("login_id").eq("login_id", login_id).execute()
    if existing.data:
        return HTMLResponse("<h2>Error: Login ID already exists</h2>", status_code=400)

    supabase.table("user_settings").insert({
        "login_id": login_id,
        "password": password,
        "bot_token": bot_token,
        "strategy": strategy,
        "trading_type": trading_type,
        "risk_percent": risk_percent,
        "total_trades": 0,
        "total_wins": 0,
        "total_losses": 0,
        "win_rate": 0,
        "bot_status": "inactive",
        "lifetime": False
    }).execute()

    return RedirectResponse("/login", status_code=303)


# ============================================
# User Login Form (GET)
# ============================================
@app.get("/login", response_class=HTMLResponse)
async def login_form():
    html = """
    <h1>Login</h1>
    <form method="post" action="/login">
        <label>Login ID:</label>
        <input type="text" name="login_id" required><br><br>
        <label>Password:</label>
        <input type="password" name="password" required><br><br>
        <button type="submit">Login</button>
    </form>
    <p>Don't have an account? <a href="/register">Register here</a></p>
    """
    return HTMLResponse(content=html)


# ============================================
# Handle User Login (POST)
# ============================================
@app.post("/login", response_class=HTMLResponse)
async def login_user(request: Request, login_id: str = Form(...), password: str = Form(...)):
    result = supabase.table("user_settings").select("*").eq("login_id", login_id).eq("password", password).execute()
    if not result.data:
        return HTMLResponse("<h2>Invalid login credentials</h2>", status_code=401)

    request.session["user"] = result.data[0]
    return RedirectResponse("/dashboard", status_code=303)


# ============================================
# Change Password (User)
# ============================================
@app.get("/change-password", response_class=HTMLResponse)
async def change_password_form(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=303)
    html = """
    <h1>Change Password</h1>
    <form method="post" action="/change-password">
        <label>Current Password:</label>
        <input type="password" name="current_password" required><br><br>
        <label>New Password:</label>
        <input type="password" name="new_password" required><br><br>
        <button type="submit">Update Password</button>
    </form>
    <p><a href="/dashboard">Back to Dashboard</a></p>
    """
    return HTMLResponse(content=html)


@app.post("/change-password", response_class=HTMLResponse)
async def change_password(request: Request, current_password: str = Form(...), new_password: str = Form(...)):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Verify current password
    result = supabase.table("user_settings").select("*").eq("login_id", user["login_id"]).eq("password", current_password).execute()
    if not result.data:
        return HTMLResponse("<h2>Current password is incorrect</h2>", status_code=400)

    # Update password
    supabase.table("user_settings").update({"password": new_password}).eq("login_id", user["login_id"]).execute()

    # Update session data
    user["password"] = new_password
    request.session["user"] = user

    return HTMLResponse("<h2>Password updated successfully</h2><p><a href='/dashboard'>Go Back</a></p>")


# ============================================
# Root Route
# ============================================
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        with open("templates/index.html", "r") as file:
            content = file.read()
        content = content.replace("{{ telegram_link }}", TELEGRAM_LINK or "#")
        content = content.replace("{{ discord_link }}", DISCORD_LINK or "#")
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: index.html not found</h1>", status_code=404)


# ============================================
# Admin Login
# ============================================
@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request):
    try:
        with open("templates/admin_login.html", "r") as file:
            return HTMLResponse(content=file.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin_login.html not found</h1>", status_code=404)


@app.post("/admin", response_class=HTMLResponse)
async def admin_auth(request: Request, login_id: str = Form(...), password: str = Form(...)):
    if login_id == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        request.session["admin_logged_in"] = True
        return RedirectResponse("/admin/dashboard", status_code=303)
    try:
        with open("templates/admin_login.html", "r") as file:
            return HTMLResponse(content=file.read().replace("{{ error }}", "Invalid login credentials. Please try again."))
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin_login.html not found</h1>", status_code=404)


# ============================================
# Admin Dashboard
# ============================================
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)
    try:
        result = supabase.table("user_settings").select("*").execute()
        users = result.data if hasattr(result, 'data') else []
        with open("templates/admin.html", "r") as file:
            content = file.read()
        user_rows = ""
        for user in users:
            user_rows += f"""
            <tr>
              <td>{user['login_id']}</td>
              <td>{user['strategy']}</td>
              <td>{user['trading_type']}</td>
              <td>{user['risk_percent']}</td>
              <td>{user['total_trades']}</td>
              <td>{user['total_wins']}</td>
              <td>{user['total_losses']}</td>
              <td>{user['win_rate']}%</td>
            </tr>
            """
        content = content.replace("{% for user in users %}{% endfor %}", user_rows)
        return HTMLResponse(content=content)
    except Exception as e:
        return HTMLResponse(f"<h2>Error loading admin dashboard: {str(e)}</h2>", status_code=500)


# ============================================
# Admin Add User
# ============================================
@app.get("/admin/add-user", response_class=HTMLResponse)
async def admin_add_user_form(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)
    try:
        with open("templates/admin_add_user.html", "r") as file:
            return HTMLResponse(content=file.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin_add_user.html not found</h1>", status_code=404)


@app.post("/admin/add-user", response_class=HTMLResponse)
async def admin_add_user(
    request: Request,
    login_id: str = Form(...),
    password: str = Form(...),
    bot_token: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...)
):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)

    if not (1 <= risk_percent <= 5):
        return HTMLResponse("<h2>Error: Risk % must be between 1 and 5</h2>", status_code=400)

    existing = supabase.table("user_settings").select("login_id").eq("login_id", login_id).execute()
    if existing.data:
        return HTMLResponse("<h2>Error: Login ID already exists</h2>", status_code=400)

    supabase.table("user_settings").insert({
        "login_id": login_id,
        "password": password,
        "bot_token": bot_token,
        "strategy": strategy,
        "trading_type": trading_type,
        "risk_percent": risk_percent,
        "total_trades": 0,
        "total_wins": 0,
        "total_losses": 0,
        "win_rate": 0,
        "bot_status": "inactive",
        "lifetime": False
    }).execute()

    return RedirectResponse("/admin/dashboard", status_code=303)
