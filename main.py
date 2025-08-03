import os
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from fastapi.templating import Jinja2Templates
from sqlalchemy.future import select
from database import User, Trade, get_db, init_db

# === Environment Load ===
load_dotenv()

# === FastAPI Setup ===
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "supersecret"))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory=".")

# === Env Variables ===
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK")
DISCORD_LINK = os.getenv("DISCORD_LINK")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# === On Startup Create Tables ===
@app.on_event("startup")
async def startup():
    await init_db()

# === Home Page ===
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK,
        "message": None
    })

@app.head("/")
async def head_root():
    return Response(status_code=200)

# === Submit Bot Config ===
@app.post("/submit", response_class=HTMLResponse)
async def submit(
    request: Request,
    bot_token: str = Form(...),
    login_id: str = Form(...),
    strategy: str = Form(...),
    password: str = Form(...),
    remember_me: str = Form(None),
    db: Depends(get_db)
):
    if password != ADMIN_PASSWORD:
        return HTMLResponse("<h2>Access Denied ❌ - Invalid Password</h2>", status_code=401)

    result = await db.execute(select(User).where(User.login_id == login_id))
    user = result.scalars().first()

    if not user:
        user = User(login_id=login_id, bot_token=bot_token, strategy=strategy)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    trade1 = Trade(user_id=user.id, symbol="BTC", result="+2.3%")
    trade2 = Trade(user_id=user.id, symbol="ETH", result="-1.1%")
    trade3 = Trade(user_id=user.id, symbol="SOL", result="+4.2%")
    db.add_all([trade1, trade2, trade3])
    await db.commit()

    request.session["user"] = {
        "login_id": login_id
    }

    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK,
        "message": "✅ Bot configuration submitted and saved."
    })

# === Admin ===
@app.get("/admin", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "error": None
    })

@app.post("/admin", response_class=HTMLResponse)
async def admin_auth(
    request: Request,
    login_id: str = Form(...),
    password: str = Form(...),
    remember_me: str = Form(None)
):
    if login_id == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        request.session["admin_logged_in"] = True
        return RedirectResponse("/admin/dashboard", status_code=303)

    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "error": "Invalid login credentials. Please try again."
    })

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Depends(get_db)):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin", status_code=303)

    result = await db.execute(select(User))
    users = result.scalars().all()

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "submissions": users
    })

# === User Dashboard ===
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Depends(get_db)):
    user_data = request.session.get("user")
    if not user_data:
        return RedirectResponse("/", status_code=303)

    result = await db.execute(select(User).where(User.login_id == user_data["login_id"]))
    user = result.scalars().first()
    if not user:
        return HTMLResponse("<h2>User not found</h2>", status_code=404)

    return templates.TemplateResponse("user_dashboard.html", {
        "request": request,
        "user": user,
        "logs": [f"{trade.symbol} {trade.result}" for trade in user.trades]
    })

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
