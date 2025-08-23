import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI(title="ProfitPilotAI", version="0.1")

# Static & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Sessions
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie="ppai_sess", max_age=60*60*12)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

@app.get("/")
def login_page(request: Request):
    if request.session.get("auth_ok"):
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["auth_ok"] = True
        request.session["user"] = username
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)

@app.get("/admin")
def admin_dashboard(request: Request):
    if not request.session.get("auth_ok"):
        return RedirectResponse("/", status_code=302)
    health = {"status": "ok"}
    return templates.TemplateResponse("admin.html", {"request": request, "health": health})

@app.get("/health")
def health():
    return {"status": "ok", "service": "profitpilotai"}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
