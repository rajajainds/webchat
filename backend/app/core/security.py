# Password hashing (argon2id) and JWT helpers.
import asyncio
from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from app.config import settings

_hasher = PasswordHash.recommended()  # argon2id
DUMMY_HASH = _hasher.hash("not-a-real-password")  # keeps login timing equal for unknown users


async def hash_password(p: str) -> str:
    return await asyncio.to_thread(_hasher.hash, p)  # CPU heavy: keep off the event loop


async def verify_password(p: str, h: str) -> bool:
    return await asyncio.to_thread(_hasher.verify, p, h)


def make_token(sub: str, kind: str, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(sub), "type": kind, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def read_token(token: str, kind: str) -> dict:
    """Raises jwt.PyJWTError if bad, expired, or the wrong kind of token."""
    p = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
    if p.get("type") != kind:
        raise jwt.InvalidTokenError("wrong token type")
    return p
