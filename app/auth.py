import secrets
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
bearerscheme = HTTPBearer()

SESSION_TTL = int(os.getenv("SESSION_TTL_MINUTES", "15")) * 60

# In-memory session store (pro MVP dostačující)
_sessions: dict[str, datetime] = {}


def hash_pin(pin: str) -> str:
    return pwd_context.hash(pin)


def verify_pin(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_session_token() -> str:
    token = secrets.token_hex(32)
    _sessions[token] = datetime.utcnow() + timedelta(seconds=SESSION_TTL)
    return token


def invalidate_expired_sessions():
    now = datetime.utcnow()
    expired = [t for t, exp in _sessions.items() if exp < now]
    for t in expired:
        del _sessions[t]


def require_parent(
    credentials: HTTPAuthorizationCredentials = Security(bearerscheme),
) -> str:
    """FastAPI dependency – ověří platný session token rodiče."""
    invalidate_expired_sessions()
    token = credentials.credentials
    if token not in _sessions or _sessions[token] < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Neplatný nebo vypršelý token. Zadejte PIN znovu.")
    return token
