from fastapi import FastAPI, Request, Form, Depends
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
    # Fetch user from Supabase
    res = supabase.table("user_settings").select("*").eq("login_id", username).execute()
    if not res.data:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"})
    
    user = res.data[0]
    if not pwd_context.verify(password, user["password"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"})

    # Successful login → send to dashboard
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    # Get all users
    users = supabase.table("user_settings").select("*").execute()
    return templates.TemplateResponse("admin.html", {"request": request, "users": users.data})


@app.post("/admin/add-user")
async def admin_add_user(
    username: str = Form(...),
    password: str = Form(...),
    strategy: str = Form(...),
    trading_type: str = Form(...),
    risk_percent: int = Form(...)
):
    try:
        hashed_password = hash_password(password)

        # Insert user into Supabase
        supabase.table("user_settings").insert({
            "login_id": username,
            "password": hashed_password,
            "strategy": strategy,
            "trading_type": trading_type,
            "risk_percent": risk_percent,
            "total_trades": 0,
            "total_wins": 0,
            "total_losses": 0,
            "lifetime": False,
            "bot_status": "inactive"
        }).execute()

        return RedirectResponse(url="/admin", status_code=303)

    except Exception as e:
        return {"error": str(e)}


@app.post("/change-password")
async def change_password(username: str = Form(...), new_password: str = Form(...)):
    hashed_password = hash_password(new_password)
    supabase.table("user_settings").update({"password": hashed_password}).eq("login_id", username).execute()
    return {"status": "Password updated successfully"}
