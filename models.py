# models.py

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    login_id = Column(String, unique=True, index=True)
    bot_token = Column(String)
    strategy = Column(String, default="Scalping")   # Day Trading / Swing Trading / Scalping
    method = Column(String, default="Forex")        # Forex / Binary
    risk_percent = Column(Integer, default=1)       # 1 - 5
    created_at = Column(DateTime, default=datetime.utcnow)

    trades = relationship("Trade", back_populates="user")

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    symbol = Column(String)
    entry_price = Column(Float)
    exit_price = Column(Float)
    result = Column(Float)          # % change
    win = Column(Integer)           # 1 = win, 0 = loss
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="trades")
