import os
import asyncio
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.templating import Jinja2Templates

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (logo, CSS)
app.mount("/static", StaticFiles(directory="."), name="static")

templates = Jinja2Templates(directory=".")

# Store paid users and credentials in memory (use a DB in production)
PAID_USERS = set()
USER_CREDENTIALS = {}
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "profitpilot123")

TELEGRAM_LINK = os.environ.get("TELEGRAM_LINK", "#")
DISCORD_LINK = os.environ.get("DISCORD_LINK", "#")


class NowPaymentsWebhook(BaseModel):
    payment_status: str
    price_amount: float
    pay_address: str
    order_id: str
    payment_id: str
    ipn_type: str
    payment_amount: float
    payment_currency: str
    order_description: str


@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "paid": False,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK
    })


@app.post("/submit")
async def submit(
    request: Request,
    email: str = Form(...),
    login_id: str = Form(...),
    password: str = Form(...),
    strategy: str = Form(...),
    admin_password: str = Form(None)
):
    if admin_password == ADMIN_PASSWORD:
        PAID_USERS.add(email)
    elif email not in PAID_USERS:
        return HTMLResponse("❌ You must pay to unlock access.", status_code=403)

    USER_CREDENTIALS[email] = {
        "login_id": login_id,
        "password": password,
        "strategy": strategy
    }

    return HTMLResponse(f"✅ Access granted! Bot will use: {strategy.upper()} strategy.")


@app.post("/nowpayments-webhook")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        webhook_data = NowPaymentsWebhook(**data)

        if webhook_data.payment_status == "confirmed":
            email = webhook_data.order_description.strip()
            PAID_USERS.add(email)
            print(f"✅ Payment confirmed for {email}")
        return JSONResponse({"status": "received"})

    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/admin/list-users")
async def list_users(admin: str = ""):
    if admin != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"paid_users": list(PAID_USERS), "credentials": USER_CREDENTIALS}
