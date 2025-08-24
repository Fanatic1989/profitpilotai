from fastapi.responses import HTMLResponse, RedirectResponse
import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
import uvicorn
from .supabase_utils import get_client, get_user_by_login_or_email, is_rate_limited, record_failed_attempt, clear_attempts, get_user_and_latest_sub, is_subscription_active
from .emailer import send_email
from .auth import create_user, verify_email_token, start_password_reset, finish_password_reset
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from .nowpayments import create_invoice, verify_ipn_signature
from .supabase_utils import get_client, add_days_from_current_end, get_user_and_latest_sub, is_subscription_active
from .auth import create_user, get_user_by_email, verify_pwd, set_role_admin
from datetime import datetime, timezone, timedelta
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi import FastAPI, Request, Form, HTTPException
from loguru import logger

app = FastAPI(title="ProfitPilotAI", version="0.1")

# Static & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Sessions
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie="ppai_sess", max_age=60*60*12, https_only=True, same_site="lax")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

@app.get("/")
def login_page(request: Request):
    if request.session.get("auth_ok"):
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    ip = request.client.host if request.client else "unknown"
    MAX_ATTEMPTS = 5
    WINDOW = 600
    if is_rate_limited(ip, MAX_ATTEMPTS, WINDOW):
        return HTMLResponse("<h3>Too many attempts. Try again later.</h3>", status_code=429)

    sb = get_client()
    u = get_user_by_login_or_email(username) if sb else None
    if not u:
        record_failed_attempt(ip, MAX_ATTEMPTS, WINDOW)
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    if not u.get("email_verified"):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Please verify your email first"})

    from passlib.hash import bcrypt
    try:
        if not bcrypt.verify(password, u["password_hash"]):
            record_failed_attempt(ip, MAX_ATTEMPTS, WINDOW)
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    except Exception:
        record_failed_attempt(ip, MAX_ATTEMPTS, WINDOW)
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

    request.session["auth_ok"] = True
    request.session["user"] = u["email"]
    clear_attempts(ip)
    # admin to /_admin; others to /dashboard
    return RedirectResponse("/_admin" if u.get("role") == "admin" else "/dashboard", status_code=302)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)

@app.get("/_admin")
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

def _require_admin(request: Request):
    if not request.session.get("auth_ok"):
        raise HTTPException(status_code=404, detail="Not found")

@app.head("/")
def head_root():
    return HTMLResponse("", status_code=200)

# --- Admin dashboard + Supabase user management ---
from .supabase_utils import grant_user, delete_user, list_active_users

@app.get("/_admin")
def admin_dashboard(request: Request):
    _require_admin(request)
    active = list_active_users()
    users = active.get("data") if active.get("ok") else []
    err = active.get("error") if not active.get("ok") else None
    return templates.TemplateResponse("admin.html", {"request": request, "health": {"status":"ok"}, "users": users, "err": err})

@app.post("/_admin/users/add")
def admin_add_user(request: Request, email: str = Form(...), plan: str = Form(...)):
    _require_admin(request)
    res = grant_user(email, plan)
    if not res.get("ok"):
        logger.error("Add user failed: {}", res.get("error"))
    return RedirectResponse("/dashboard" if request.session.get("user") != os.getenv("ADMIN_USERNAME","admin") else "/_admin", status_code=302)

@app.post("/_admin/users/delete")
def admin_delete_user(request: Request, email: str = Form(...)):
    _require_admin(request)
    res = delete_user(email)
    if not res.get("ok"):
        logger.error("Delete user failed: {}", res.get("error"))
    return RedirectResponse("/dashboard" if request.session.get("user") != os.getenv("ADMIN_USERNAME","admin") else "/_admin", status_code=302)

@app.get("/register")
def register_page(request: Request):
    if request.session.get("auth_ok"):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})

@app.get("/dashboard")
def user_dashboard(request: Request):
    if not request.session.get("auth_ok"):
        return RedirectResponse("/", status_code=302)
    email = request.session.get("user")
    sb = get_client()
    if not sb:
        return templates.TemplateResponse("user.html", {"request": request, "sub": None})
    try:
        u = sb.table("app_users").select("id,role").eq("email", email).single().execute().data
        sub = sb.table("subscriptions").select("*").eq("user_id", u["id"]).order("created_at", desc=True).limit(1).execute().data
        sub = sub[0] if sub else None
    except Exception:
        sub = None
    return templates.TemplateResponse("user.html", {"request": request, "sub": sub})

@app.head("/uptime")
def uptime_head():
    return HTMLResponse("", status_code=200)

@app.get("/uptime")
def uptime_get():
    return {"ok": True}

@app.post("/crypto/subscribe")
async def crypto_subscribe(request: Request):
    if not request.session.get("auth_ok"):
        return RedirectResponse("/", status_code=302)
    email = request.session.get("user")
    url = await create_invoice(email=email, price_amount=100.0, price_currency="usd")
    if not url:
        return HTMLResponse("<h3>Crypto payments not configured.</h3>", status_code=500)
    return RedirectResponse(url, status_code=303)

@app.post("/crypto/ipn")
async def crypto_ipn(request: Request):
    raw = await request.body()
    sig = request.headers.get("x-nowpayments-sig", "")
    ok = verify_ipn_signature(raw, sig)
    if not ok:
        logger.warning("Invalid NOWPayments signature")
        return JSONResponse({"ok": False, "error": "bad signature"}, status_code=400)

    data = await request.json()
    # Typical statuses: waiting, confirming, confirmed, finished, failed, refunded
    payment_status = data.get("payment_status")
    order_id = data.get("order_id","")
    invoice_id = data.get("invoice_id")
    pay_currency = data.get("pay_currency")
    price_amount = data.get("price_amount")
    email = order_id.replace("ppai-","") if order_id.startswith("ppai-") else None

    if not email:
        return JSONResponse({"ok": False, "error": "no email"}, status_code=400)

    # Activate only when "finished" (paid and confirmed)
    if payment_status in ("finished", "confirmed"):
        sb = get_client()
        if not sb:
            return JSONResponse({"ok": False, "error": "Supabase not configured"}, status_code=500)
        try:
            u = sb.table("app_users").select("id,email").eq("email", email).single().execute().data
            # Auto-extend 30 days from later of (now, current end)
            add_days_from_current_end(u["id"], days=30)
        except Exception as e:
            logger.exception("crypto ipn update failed")
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return JSONResponse({"ok": True})

FAILED_LOGINS = {}
MAX_ATTEMPTS = 5
WINDOW = 600  # 10 minutes

@app.get("/robots.txt")
def robots():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("User-agent: *\nDisallow: /_admin\n", status_code=200)

@app.post("/register")
def register_post(request: Request, name: str = Form(...), address: str = Form(...), login_id: str = Form(...), email: str = Form(...), password: str = Form(...)):
    ok, token_or_err = create_user(name, address, login_id, email, password)
    if not ok:
        return templates.TemplateResponse("register.html", {"request": request, "error": f"Registration failed: {token_or_err}"})
    verify_link = f"{os.getenv('SITE_BASE','http://localhost:8000')}/verify?token={token_or_err}"
    send_email(email, "Verify your ProfitPilotAI account", f"<p>Hi {name},</p><p>Click to verify: <a href='{verify_link}'>Verify</a></p>")
    return templates.TemplateResponse("verify_sent.html", {"request": request, "email": email})

@app.get("/verify")
def verify(token: str):
    if verify_email_token(token):
        return templates.TemplateResponse("verify_done.html", {"request": {}})
    return templates.TemplateResponse("verify_error.html", {"request": {}}, status_code=400)

@app.get("/forgot")
def forgot_page(request: Request):
    return templates.TemplateResponse("forgot.html", {"request": request, "error": None})

@app.post("/forgot")
def forgot_start(request: Request, login_or_email: str = Form(...)):
    token = start_password_reset(login_or_email)
    if not token:
        return templates.TemplateResponse("forgot.html", {"request": request, "error": "Account not found"})
    link = f"{os.getenv('SITE_BASE','http://localhost:8000')}/reset?token={token}"
    # send email (best effort)
    send_email(login_or_email, "Reset your ProfitPilotAI password", f"<p>Click to reset: <a href='{link}'>Reset password</a></p>")
    return HTMLResponse("<h3>Check your email for a reset link.</h3>")

@app.get("/reset")
def reset_page(request: Request, token: str):
    return templates.TemplateResponse("reset.html", {"request": request, "token": token, "error": None})

@app.post("/reset")
def reset_do(request: Request, token: str, password: str = Form(...)):
    if finish_password_reset(token, password):
        return HTMLResponse("<h3>Password updated. You can now <a href='/'>sign in</a>.</h3>")
    return templates.TemplateResponse("reset.html", {"request": request, "token": token, "error": "Invalid or expired token"}, status_code=400)


@app.get("/_debug/versions")
def _debug_versions():
    import sys, pkgutil, importlib
    wanted = ["httpx","supabase","gotrue","httpcore","starlette","fastapi"]
    out = {}
    for name in wanted:
        try:
            m = importlib.import_module(name)
            out[name] = getattr(m, "__version__", "unknown")
        except Exception as e:
            out[name] = f"missing: {e}"
    out["python"] = sys.version
    return out

@app.get("/_ping")
def ping():
    return {"ok": True}


@app.get("/admin/users")
def admin_users(request: Request):
    if not request.session.get("auth_ok") or request.session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    users = list_active_users()
    return templates.TemplateResponse("admin_users.html", {"request": request, "users": users})

@app.post("/admin/users/grant")
def admin_grant(request: Request, identifier: str = Form(...), plan: str = Form(...)):
    if not request.session.get("auth_ok") or request.session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    ok = grant_user(identifier, plan)
    msg = "Granted" if ok else "Failed"
    users = list_active_users()
    return templates.TemplateResponse("admin_users.html", {"request": request, "users": users, "flash": f"{msg} {identifier} => {plan}"})

@app.post("/admin/users/delete")
def admin_delete(request: Request, identifier: str = Form(...)):
    if not request.session.get("auth_ok") or request.session.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    ok = delete_user(identifier)
    msg = "Deleted" if ok else "Failed"
    users = list_active_users()
    return templates.TemplateResponse("admin_users.html", {"request": request, "users": users, "flash": f"{msg} {identifier}"})


@app.get("/admin")
def admin_home(request: Request):
    if not request.session.get("auth_ok"):
        return RedirectResponse(url="/login", status_code=302)
    if request.session.get("role") != "admin":
        return HTMLResponse("<h3>Forbidden</h3>", status_code=403)
    return templates.TemplateResponse("admin.html", {"request": request})
