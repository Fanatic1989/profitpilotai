from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "defaultsecret"))

# Mount static files (like style.css, logo.png)
app.mount("/static", StaticFiles(directory="."), name="static")

templates = Jinja2Templates(directory=".")

# Load admin password from .env
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/admin")
def admin_login(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin")
def admin_auth(request: Request, login_id: str = Form(...), password: str = Form(...)):
    if login_id == "admin" and password == ADMIN_PASSWORD:
        return templates.TemplateResponse("admin.html", {"request": request})
    return RedirectResponse("/admin", status_code=303)
