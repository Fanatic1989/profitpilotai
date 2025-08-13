from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from supabase import create_client
import os

app = FastAPI()

# UptimeRobot HEAD check
@app.head("/")
async def head_check():
    return {"status": "ok"}

# Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# Templates & Static
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --------------------------
# Routes
# --------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    res = supabase.table("user_settings").select("*").eq("login_id", username).execute()
    if not res.data or not pwd_context.verify(password, res.data[0]["password"]):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })
    
    user = res.data[0]
    response = templates.TemplateResponse("dashboard.html", {"request": request, "user": user})
    response.set_cookie(key="username", value=username, httponly=True, max_age=3600)
    return response

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    users = supabase.table("user_settings").select("*").execute()
    return templates.TemplateResponse("admin.html", {"request": request, "users": users.data})

@app.post("/admin/add-user")
async def admin_add_user(
    login_id: str = Form(...),
    bot_token: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...),
    password: str = Form(...),
    lifetime: str = Form(None)
):
    hashed_password = hash_password(password)
    lifetime_status = True if lifetime == "true" else False

    supabase.table("user_settings").insert({
        "login_id": login_id,
        "bot_token": bot_token,
        "password": hashed_password,
        "strategy": strategy,
        "trading_type": trading_type,
        "risk_percent": risk_percent,
        "total_trades": 0,
        "total_wins": 0,
        "total_losses": 0,
        "lifetime": lifetime_status,
        "bot_status": "inactive"
    }).execute()

    return RedirectResponse(url="/admin", status_code=303)

@app.get("/user/change-password", response_class=HTMLResponse)
async def change_password_form(request: Request):
    username = request.cookies.get("username")
    if not username:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("change_password.html", {"request": request, "username": username})

@app.post("/user/change-password")
async def change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    username = request.cookies.get("username")
    if not username:
        return RedirectResponse(url="/")

    if new_password != confirm_password:
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "username": username,
            "error": "New passwords do not match"
        })

    res = supabase.table("user_settings").select("*").eq("login_id", username).execute()
    if not res.data:
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "username": username,
            "error": "User not found"
        })

    user = res.data[0]
    if not pwd_context.verify(old_password, user["password"]):
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "username": username,
            "error": "Old password is incorrect"
        })

    hashed_password = hash_password(new_password)
    supabase.table("user_settings").update({"password": hashed_password}).eq("login_id", username).execute()

    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("username")
    return response
