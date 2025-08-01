from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI()

# Serve static files (style.css, logo.png, etc.)
app.mount("/static", StaticFiles(directory="."), name="static")

# Jinja2 templates setup
templates = Jinja2Templates(directory=".")

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "supersecret"))

# Admin password
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "hardcoded123")

# Handle HEAD request (for UptimeRobot)
@app.head("/", response_class=PlainTextResponse)
async def head_check():
    return PlainTextResponse("OK", status_code=200)

# Home page (User login view)
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Admin panel page
@app.get("/admin", response_class=HTMLResponse)
async def admin_view(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

# Handle form submission from /admin
@app.post("/submit", response_class=HTMLResponse)
async def submit_admin_data(
    request: Request,
    bot_token: str = Form(...),
    login_id: str = Form(...),
    strategy: str = Form(...),
    password: str = Form(...)
):
    if password != ADMIN_PASSWORD:
        return HTMLResponse(content="<h3>Invalid Admin Password</h3>", status_code=401)

    # Simulate storing the bot config
    print("Received bot config:")
    print(f"Bot Token: {bot_token}")
    print(f"Login ID: {login_id}")
    print(f"Strategy: {strategy}")

    return HTMLResponse(content="<h3>Bot setup received!</h3>", status_code=200)

# Handle user login (can be expanded later)
@app.post("/login", response_class=HTMLResponse)
async def user_login(request: Request, login_id: str = Form(...), password: str = Form(...)):
    # Placeholder login logic
    if login_id and password:
        return HTMLResponse(content=f"<h3>Welcome {login_id}! Your bot will activate shortly.</h3>", status_code=200)
    return HTMLResponse(content="<h3>Missing credentials.</h3>", status_code=400)
