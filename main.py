from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "hardcoded_secret"))

# Mount static files from the current folder
app.mount("/static", StaticFiles(directory="."), name="static")

templates = Jinja2Templates(directory=".")

TELEGRAM_LINK = os.getenv("TELEGRAM_LINK", "#")
DISCORD_LINK = os.getenv("DISCORD_LINK", "#")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK
    })
