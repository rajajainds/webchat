# Token issuing. Access token = short JWT. Refresh token = random string,
# only its sha256 hash is stored, and it is single-use (rotated on every refresh).
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.security import make_token
from app.models.user import RefreshToken, User


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # sqlite (tests) returns naive


async def issue_tokens(db: AsyncSession, user: User) -> dict:
    now = datetime.now(timezone.utc)
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.expires_at < now))
    refresh = secrets.token_urlsafe(48)
    db.add(RefreshToken(user_id=user.id, token_hash=_hash(refresh), expires_at=now + timedelta(days=settings.refresh_days)))
    await db.commit()
    return {"access_token": make_token(user.id, "access", settings.access_minutes), "refresh_token": refresh}


async def rotate_refresh(db: AsyncSession, refresh: str) -> dict:
    row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(refresh)))
    if not row or _utc(row.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired. Please log in again.")
    user = await db.get(User, row.user_id)
    await db.delete(row)  # old token dies here
    return await issue_tokens(db, user)  # commits the delete too


async def revoke_refresh(db: AsyncSession, refresh: str) -> None:
    await db.execute(delete(RefreshToken).where(RefreshToken.token_hash == _hash(refresh)))
    await db.commit()
