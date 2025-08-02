# === Upgrade Plan: Enable Real Trade Logging with SQLite (Option B+C) ===

# STEP 1: Install SQLite-related dependencies
# pip install sqlalchemy aiosqlite

# STEP 2: Create the database models using SQLAlchemy

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    login_id = Column(String, unique=True, index=True)
    bot_token = Column(String)
    strategy = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    trades = relationship("Trade", back_populates="user")

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    symbol = Column(String)
    result = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="trades")

# STEP 3: Setup SQLite async engine and session
DATABASE_URL = "sqlite+aiosqlite:///./database.db"
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# STEP 4: Create DB tables (one-time migration logic)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# STEP 5: Replace in-memory logic in /submit with real database writes
from fastapi import Depends

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.post("/submit", response_class=HTMLResponse)
async def submit(
    request: Request,
    bot_token: str = Form(...),
    login_id: str = Form(...),
    strategy: str = Form(...),
    password: str = Form(...),
    remember_me: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    if password != ADMIN_PASSWORD:
        return HTMLResponse("<h2>Access Denied ❌ - Invalid Password</h2>", status_code=401)

    # Check if user exists
    from sqlalchemy.future import select
    result = await db.execute(select(User).where(User.login_id == login_id))
    user = result.scalars().first()

    if not user:
        user = User(login_id=login_id, bot_token=bot_token, strategy=strategy)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Sample trade logs (in real use, push from trading bot API/webhook)
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

# STEP 6: Pull user trade logs from DB for dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
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
