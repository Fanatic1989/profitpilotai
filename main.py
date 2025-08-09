import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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

# Initialize Jinja2Templates
templates = Jinja2Templates(directory="templates")

# === ENV Vars ===
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK")
DISCORD_LINK = os.getenv("DISCORD_LINK")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


@app.on_event("startup")
async def startup():
    print("Application started successfully!")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "telegram_link": TELEGRAM_LINK or "#",
                "discord_link": DISCORD_LINK or "#"
            }
        )
    except Exception as e:
        return HTMLResponse(f"<h1>Error loading index.html: {str(e)}</h1>", status_code=500)


@app.head("/")
async def head_root():
    return Response(status_code=200)


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
        return templates.TemplateResponse("admin_login.html", {"request": request})
    except Exception as e:
        return HTMLResponse(f"<h1>Error loading admin_login.html: {str(e)}</h1>", status_code=500)


@app.post("/admin", response_class=HTMLResponse)
async def admin_auth(request: Request, login_id: str = Form(...), password: str = Form(...)):
    if login_id == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        request.session["admin_logged_in"] = True
        return RedirectResponse("/admin/dashboard", status_code=303)

    try:
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "error": "Invalid login credentials. Please try again."}
        )
    except Exception as e:
        return HTMLResponse(f"<h1>Error loading admin_login.html: {str(e)}</h1>", status_code=500)


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)

    try:
        result = supabase.table("user_settings").select("*").execute()
        users = result.data if hasattr(result, 'data') else []

        return templates.TemplateResponse(
            "admin.html",
            {"request": request, "users": users}
        )

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


@app.get("/admin/edit-user/{login_id}", response_class=HTMLResponse)
async def edit_user(request: Request, login_id: str):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)

    try:
        # Fetch the user data from Supabase
        result = supabase.table("user_settings").select("*").eq("login_id", login_id).single().execute()
        user = result.data if hasattr(result, 'data') else None

        if not user:
            return HTMLResponse("<h2>User not found</h2>", status_code=404)

        # Render the edit form template
        return templates.TemplateResponse(
            "edit_user.html",
            {"request": request, "user": user}
        )

    except Exception as e:
        return HTMLResponse(f"<h2>Error loading edit page: {str(e)}</h2>", status_code=500)


@app.post("/admin/update-user/{login_id}", response_class=HTMLResponse)
async def update_user(
    request: Request,
    login_id: str,
    bot_token: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...)
):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)

    try:
        # Update the user data in Supabase
        supabase.table("user_settings").update({
            "bot_token": bot_token,
            "strategy": strategy,
            "trading_type": trading_type,
            "risk_percent": risk_percent
        }).eq("login_id", login_id).execute()

        return RedirectResponse("/admin/dashboard", status_code=303)

    except Exception as e:
        return HTMLResponse(f"<h2>Error updating user: {str(e)}</h2>", status_code=500)


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

        return templates.TemplateResponse(
            "user_dashboard.html",
            {
                "request": request,
                "user": user_data,
                "stats": stats
            }
        )

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
@app.post("/admin/toggle-lifetime/{login_id}", response_class=JSONResponse)
async def toggle_lifetime(request: Request, login_id: str):
    if not request.session.get("admin_logged_in"):
        return JSONResponse({"success": False, "message": "Unauthorized"}, status_code=401)

    try:
        result = supabase.table("user_settings").select("lifetime").eq("login_id", login_id).single().execute()
        current_status = result.data.get("lifetime", False)
        new_status = not current_status

        supabase.table("user_settings").update({"lifetime": new_status}).eq("login_id", login_id).execute()
        return JSONResponse({"success": True, "new_status": new_status})

    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@app.post("/admin/toggle-bot/{login_id}", response_class=JSONResponse)
async def toggle_bot(request: Request, login_id: str):
    if not request.session.get("admin_logged_in"):
        return JSONResponse({"success": False, "message": "Unauthorized"}, status_code=401)

    try:
        result = supabase.table("user_settings").select("bot_status").eq("login_id", login_id).single().execute()
        current_status = result.data.get("bot_status", "inactive")
        new_status = "paused" if current_status == "active" else "active"

        supabase.table("user_settings").update({"bot_status": new_status}).eq("login_id", login_id).execute()
        return JSONResponse({"success": True, "new_status": new_status})

    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)
