# Shared FastAPI dependencies: DB session and "who is calling".
import uuid
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import read_token
from app.db.postgres import SessionLocal
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


async def get_db():
    async with SessionLocal() as session:
        yield session


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncSession = Depends(get_db)
) -> User:
    if not creds:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = read_token(creds.credentials, "access")
        user = await db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "Invalid or expired token")
    if not user:
        raise HTTPException(401, "Invalid or expired token")
    return user


async def complete_user(user: User = Depends(current_user)) -> User:
    if not user.profile_complete:  # chat features need a profile first
        raise HTTPException(403, "Complete your profile first")
    return user
