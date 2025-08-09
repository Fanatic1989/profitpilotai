import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
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

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        with open("templates/index.html", "r") as file:  # Updated path to templates directory
            content = file.read()
        content = content.replace("{{ telegram_link }}", TELEGRAM_LINK or "#")
        content = content.replace("{{ discord_link }}", DISCORD_LINK or "#")
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: index.html not found</h1>", status_code=404)

@app.head("/")
async def head_root():
    return Response(status_code=200)  # Fixed missing import for Response

@app.post("/submit", response_class=HTMLResponse)
async def submit(
    request: Request,
    bot_token: str = Form(...),
    login_id: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...),
    password: str = Form(...)
):
    if password != ADMIN_PASSWORD:
        return HTMLResponse("<h2>Access Denied ❌ - Invalid Password</h2>", status_code=401)
    if not (1 <= risk_percent <= 5):
        return HTMLResponse("<h2>Error: Risk % must be between 1 and 5</h2>", status_code=400)
    try:
        response = supabase.table("user_settings").upsert({
            "login_id": login_id,
            "bot_token": bot_token,
            "strategy": strategy,
            "trading_type": trading_type,
            "risk_percent": risk_percent,
            "total_trades": 0,
            "total_wins": 0,
            "total_losses": 0,
            "bot_status": "active",
            "lifetime": False
        }).execute()
        if request.session.get("admin_logged_in"):
            return RedirectResponse("/admin/dashboard", status_code=303)
        request.session["user"] = {
            "login_id": login_id,
            "bot_token": bot_token,
            "strategy": strategy,
            "trading_type": trading_type,
            "risk_percent": risk_percent
        }
        return RedirectResponse("/dashboard", status_code=303)
    except Exception as e:
        return HTMLResponse(f"<h2>Server Error: {str(e)}</h2>", status_code=500)

@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request):
    try:
        with open("templates/admin_login.html", "r") as file:  # Updated path to templates directory
            return HTMLResponse(content=file.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin_login.html not found</h1>", status_code=404)

@app.post("/admin", response_class=HTMLResponse)
async def admin_auth(request: Request, login_id: str = Form(...), password: str = Form(...)):
    if login_id == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        request.session["admin_logged_in"] = True
        return RedirectResponse("/admin/dashboard", status_code=303)
    try:
        with open("templates/admin_login.html", "r") as file:  # Updated path to templates directory
            return HTMLResponse(content=file.read().replace("{{ error }}", "Invalid login credentials. Please try again."))
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: admin_login.html not found</h1>", status_code=404)

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)
    try:
        result = supabase.table("user_settings").select("*").execute()
        users = result.data if hasattr(result, 'data') else []
        with open("templates/admin.html", "r") as file:  # Updated path to templates directory
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
              <td>
                <form method='post' action='/admin/toggle-lifetime/{user['login_id']}'>
                  <button style='background-color: {'green' if user['lifetime'] else 'red'}; color: white;'>
                    {'✅' if user['lifetime'] else '❌'}
                  </button>
                </form>
              </td>
              <td>
                <form method='post' action='/admin/toggle-bot/{user['login_id']}'>
                  <button style='background-color: {'green' if user['bot_status'] == 'active' else 'gray'}; color: white;'>
                    {user['bot_status']}
                  </button>
                </form>
              </td>
              <td>
                <a href='/admin/edit-user/{user['login_id']}'>Edit</a>
                <form method='post' action='/admin/delete-user/{user['login_id']}' class='inline-form'>
                  <button onclick="return confirm('Delete this user?')">Delete</button>
                </form>
              </td>
            </tr>
            """
        content = content.replace("{% for user in users %}{% endfor %}", user_rows)
        return HTMLResponse(content=content)
    except Exception as e:
        return HTMLResponse(f"<h2>Error loading admin dashboard: {str(e)}</h2>", status_code=500)

@app.post("/admin/delete-user/{login_id}", response_class=HTMLResponse)
async def delete_user(request: Request, login_id: str):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)
    try:
        supabase.table("user_settings").delete().eq("login_id", login_id).execute()
        return RedirectResponse("/admin/dashboard", status_code=303)
    except Exception as e:
        return HTMLResponse(f"<h2>Error deleting user: {str(e)}</h2>", status_code=500)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_data = request.session.get("user")
    if not user_data:
        return RedirectResponse("/", status_code=303)
    try:
        result = supabase.table("user_settings") \
            .select("*") \
            .eq("login_id", user_data["login_id"]) \
            .limit(1) \
            .execute()
        if not result.data or not isinstance(result.data, list) or len(result.data) == 0:
            raise Exception("No matching user found in database.")
        row = result.data[0]
        stats = {
            "trading_type": row.get("trading_type", ""),
            "risk_percent": str(row.get("risk_percent", "")),
            "total_trades": row.get("total_trades", 0),
            "total_wins": row.get("total_wins", 0),
            "total_losses": row.get("total_losses", 0),
            "win_rate": row.get("win_rate", 0),
        }
        with open("templates/user_dashboard.html", "r") as file:  # Updated path to templates directory
            content = file.read()
        content = (
            content.replace("{{ user.login_id }}", user_data["login_id"])
                   .replace("{{ user.bot_token }}", user_data["bot_token"])
                   .replace("{{ user.strategy }}", user_data["strategy"])
                   .replace("{{ user.trading_type }}", stats["trading_type"])
                   .replace("{{ user.risk_percent }}", stats["risk_percent"])
                   .replace("{{ stats.total_trades }}", str(stats["total_trades"]))
                   .replace("{{ stats.total_wins }}", str(stats["total_wins"]))
                   .replace("{{ stats.total_losses }}", str(stats["total_losses"]))
                   .replace("{{ stats.win_rate }}", str(stats["win_rate"]))
        )
        return HTMLResponse(content=content)
    except Exception as e:
        return HTMLResponse(f"<h2>Error loading dashboard: {str(e)}</h2>", status_code=500)

@app.post("/update-settings", response_class=HTMLResponse)
async def update_settings(
    request: Request,
    method: str = Form(...),
    strategy: str = Form(...),
    risk: int = Form(...)
):
    user_data = request.session.get("user")
    if not user_data:
        return RedirectResponse("/", status_code=303)
    try:
        supabase.table("user_settings").update({
            "trading_type": method.lower(),
            "strategy": strategy.lower(),
            "risk_percent": risk
        }).eq("login_id", user_data["login_id"]).execute()
        user_data["strategy"] = strategy
        user_data["trading_type"] = method
        user_data["risk_percent"] = risk
        request.session["user"] = user_data
        return RedirectResponse("/dashboard", status_code=303)
    except Exception as e:
        return HTMLResponse(f"<h2>Error updating settings: {str(e)}</h2>", status_code=500)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

# === NEW ROUTES ===
@app.post("/admin/toggle-lifetime")
async def toggle_lifetime(request: Request):
    data = await request.json()
    login_id = data["login_id"]
    current = data["current"]
    new_status = not current
    supabase.table("user_settings").update({"lifetime": new_status}).eq("login_id", login_id).execute()
    return JSONResponse(content={"success": True})

@app.post("/admin/toggle-bot-status")
async def toggle_bot_status(request: Request):
    data = await request.json()
    login_id = data["login_id"]
    current = data["current"]
    new_status = "paused" if current == "active" else "active"
    supabase.table("user_settings").update({"bot_status": new_status}).eq("login_id", login_id).execute()
    return JSONResponse(content={"success": True})
