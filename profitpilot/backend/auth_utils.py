"""
backend/auth_utils.py

JWT + password hashing helpers and a FastAPI dependency to require auth.
- Uses bcrypt for password hashing and PyJWT for tokens.
- In production, set SECRET_KEY via environment variable (do NOT hardcode).
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import bcrypt
import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.getenv("JWT_SECRET", "change-this-secret")
ALGORITHM = os.getenv("JWT_ALGO", "HS256")
DEFAULT_EXPIRES_SECONDS = int(os.getenv("JWT_EXP_SECONDS", "86400"))  # 24h

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    if isinstance(password, str):
        password = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    if isinstance(password, str):
        password = password.encode("utf-8")
    if isinstance(hashed, str):
        hashed = hashed.encode("utf-8")
    try:
        return bcrypt.checkpw(password, hashed)
    except Exception:
        return False


def create_jwt_token(subject: str, expires_seconds: Optional[int] = None, extra: Optional[Dict[str, Any]] = None) -> str:
    now = datetime.utcnow()
    exp = now + timedelta(seconds=(expires_seconds or DEFAULT_EXPIRES_SECONDS))
    payload = {"sub": subject, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    # pyjwt returns str in v2+, bytes in v1; ensure str
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def decode_jwt_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    FastAPI dependency: returns decoded token payload if valid, otherwise raises 401.
    Accepts Bearer tokens.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing credentials")
    token = credentials.credentials
    if token.lower().startswith("bearer "):
        token = token[7:]
    return decode_jwt_token(token)
