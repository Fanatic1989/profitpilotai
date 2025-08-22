"""
auth_utils.py
Simple auth utilities for ProfitPilotAI:
- password hashing / verification (bcrypt)
- token creation/verification (JWT)
- a tiny decorator for FastAPI endpoints (if you wire it in main.py)
Note: In production, rotate secrets, use HTTPS, and secure cookies/headers.
"""

import os
import time
from typing import Optional, Dict, Any
from functools import wraps

import bcrypt
import jwt
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

# Config: override via environment variables
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGO", "HS256")
JWT_EXP_SECONDS = int(os.getenv("JWT_EXP_SECONDS", 3600 * 24))  # 24h

api_key_scheme = APIKeyHeader(name="Authorization", auto_error=False)


def hash_password(plain_password: str) -> str:
    if isinstance(plain_password, str):
        plain_password = plain_password.encode("utf-8")
    hashed = bcrypt.hashpw(plain_password, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if isinstance(plain_password, str):
        plain_password = plain_password.encode("utf-8")
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode("utf-8")
    try:
        return bcrypt.checkpw(plain_password, hashed_password)
    except ValueError:
        return False


def create_jwt_token(subject: str, extra: Optional[Dict[str, Any]] = None, exp_seconds: Optional[int] = None) -> str:
    now = int(time.time())
    exp = now + (exp_seconds if exp_seconds is not None else JWT_EXP_SECONDS)
    payload = {"sub": subject, "iat": now, "exp": exp}
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # jwt.encode returns str in pyjwt>=2.x
    return token


def decode_jwt_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_authorization_header(api_key: Optional[str] = None):
    """
    Helper for FastAPI dependencies. Accepts header value like "Bearer <token>" or the token itself.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if api_key.startswith("Bearer "):
        api_key = api_key[7:]
    return decode_jwt_token(api_key)


# A tiny decorator for non-FastAPI use (function-level)
def require_jwt(func):
    @wraps(func)
    def wrapper(token: str = None, *args, **kwargs):
        if not token:
            raise HTTPException(status_code=401, detail="Missing token")
        if token.startswith("Bearer "):
            token = token[7:]
        decode_jwt_token(token)
        return func(*args, **kwargs)

    return wrapper
