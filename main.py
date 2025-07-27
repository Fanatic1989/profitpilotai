import os
import httpx
import asyncio
import functools
import concurrent.futures
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

# Telegram & Discord
from telegram import Bot as TelegramBot
from telegram.error import TelegramError
import discord
from discord.ext import commands

# ==== LOAD ENV ====
load_dotenv()

PORT = int(os.environ.get("PORT", 8000))
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
NOWPAYMENTS_API_KEY = os.environ.get("NOWPAYMENTS_API_KEY")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
TELEGRAM_LINK = os.environ.get("TELEGRAM_LINK", "#")
DISCORD_LINK = os.environ.get("DISCORD_LINK", "#")

app = FastAPI()

# ==== SETUP FRONTEND TEMPLATES & STATIC FILES ====
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ==== MODELS ====
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

# ==== STATE ====
active_users = {}

# ==== TELEGRAM BOT ====
telegram_bot = TelegramBot(token=TELEGRAM_TOKEN)
executor = concurrent.futures.ThreadPoolExecutor()

async def send_telegram_message(message: str):
    try:
        await asyncio.get_event_loop().run_in_executor(
            executor,
            functools.partial(telegram_bot.send_message, chat_id=TELEGRAM_CHAT_ID, text=message)
        )
    except TelegramError as e:
        print(f"Telegram error: {e}")

def get_telegram_user_id(email: str):
    return 123456789  # Replace with actual logic

async def give_telegram_access(user_email):
    try:
        telegram_user_id = get_telegram_user_id(user_email)
        await asyncio.get_event_loop().run_in_executor(
            executor,
            functools.partial(telegram_bot.unban_chat_member, chat_id=TELEGRAM_GROUP_ID, user_id=telegram_user_id)
        )
        print(f"✅ Telegram access granted to {user_email}")
    except TelegramError as e:
        print(f"⚠️ Telegram error: {e}")

# ==== DISCORD BOT ====
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True

discord_bot = commands.Bot(command_prefix="!", intents=intents)

@discord_bot.event
async def on_ready():
    print(f"✅ Discord bot connected as {discord_bot.user}")

async def send_discord_message(message: str):
    await discord_bot.wait_until_ready()
    channel = discord_bot.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(message)
    else:
        print("❌ Discord channel not found!")

async def give_discord_access(user_email):
    guild = discord.utils.get(discord_bot.guilds, id=DISCORD_GUILD_ID)
    if guild:
        channel = guild.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            invite = await channel.create_invite(max_uses=1, unique=True)
            print(f"Discord invite for {user_email}: {invite.url}")
        else:
            print("⚠️ Discord channel not found")
    else:
        print("⚠️ Discord guild not found")

# ==== ROUTES ====
@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "telegram_link": TELEGRAM_LINK,
        "discord_link": DISCORD_LINK
    })

@app.head("/")
async def root_head():
    return JSONResponse(content={}, status_code=200)

@app.post("/nowpayments-webhook")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        webhook_data = NowPaymentsWebhook(**data)

        status = webhook_data.payment_status
        amount = webhook_data.price_amount
        currency = webhook_data.payment_currency
        user_email = webhook_data.order_description

        message = f"💰 Payment Received:\nStatus: {status}\nAmount: {amount} {currency}"

        await send_telegram_message(message)
        await send_discord_message(message)

        if status == "confirmed":
            await give_telegram_access(user_email)
            await give_discord_access(user_email)

            active_users[user_email] = {
                "paid": True,
                "timestamp": asyncio.get_event_loop().time(),
            }

        return JSONResponse(content={"status": "received"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/deactivate-user/{email}")
async def deactivate_user(email: str):
    if email not in active_users:
        raise HTTPException(status_code=404, detail="User not found")

    del active_users[email]
    print(f"⛔ User {email} deactivated")
    return {"status": "removed"}

# ==== BOT STARTUP ====
def start_discord_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(discord_bot.start(DISCORD_TOKEN))

def start_telegram_bot():
    print("✅ Telegram bot initialized.")

# ==== MAIN RUN ====
if __name__ == "__main__":
    import uvicorn
    import threading

    threading.Thread(target=start_discord_bot, daemon=True).start()
    start_telegram_bot()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
