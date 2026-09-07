"""Additive auth: hashed passwords + bearer tokens.

Per openapi.yaml, none of the 8 spec endpoints require auth (the frontend
sends no tokens). This module provides opt-in auth: register/login/me
endpoints plus an optional bearer dependency wired into the spec routers
(accepted, never enforced) so tokens can be adopted later without breakage.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from .models import UserRecord
from .protocols import UserStore
from .store import DuplicateError

SECRET_KEY = os.getenv("REVIEW_BOT_SECRET", "dev-only-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# auto_error=False -> missing/invalid Authorization header yields None,
# which is what keeps the spec endpoints open while accepting tokens.
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login", auto_error=False
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(username: str, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme_optional),
) -> str | None:
    """Bearer token if a valid one was sent, else None (never raises)."""
    return decode_access_token(token) if token else None


def register_user(store: UserStore, username: str, password: str) -> UserRecord:
    if username in store.users:
        raise DuplicateError("Username is already taken")
    record = UserRecord(username=username, password_hash=hash_password(password))
    store.users[username] = record
    return record


def authenticate_user(store: UserStore, username: str, password: str) -> UserRecord | None:
    record = store.users.get(username)
    if record is None or not verify_password(password, record.password_hash):
        return None
    return record
