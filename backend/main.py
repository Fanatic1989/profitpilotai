import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
import uvicorn
from .nowpayments import create_invoice, verify_ipn_signature
from .supabase_utils import get_client
from .payments import create_checkout_session
from .auth import create_user, get_user_by_email, verify_pwd, set_role_admin
from datetime import datetime, timezone
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi import FastAPI, Request, Form, HTTPException
from loguru import logger

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

@app.post("/register")
def register_post(request: Request, email: str = Form(...), password: str = Form(...)):
    ok, res = create_user(email, password)
    if not ok:
        return templates.TemplateResponse("register.html", {"request": request, "error": f"Registration failed: {res}"})
    # Auto-login after registration
    request.session["auth_ok"] = True
    request.session["user"] = email
    return RedirectResponse("/dashboard", status_code=302)

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
            u = sb.table("app_users").select("id").eq("email", email).single().execute().data
            # upsert a subscription row
            sb.table("subscriptions").upsert({
                "user_id": u["id"],
                "status": "active",
                "stripe_customer_id": None,
                "stripe_subscription_id": f"np_{invoice_id}",
                "current_period_end": None  # crypto plan could be treated as lifetime or handled manually
            }, on_conflict="stripe_subscription_id").execute()
        except Exception as e:
            logger.exception("crypto ipn supabase upsert failed")
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    return JSONResponse({"ok": True})
