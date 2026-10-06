# Sprint 1: own profile. Sprint 2: username search.
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.ratelimit import hit
from app.deps import complete_user, current_user, get_db
from app.models.user import User
from app.schemas.user import MeOut, ProfileIn, PublicUser

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(current_user)):
    return user


@router.put("/me/profile", response_model=MeOut)
async def save_profile(body: ProfileIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Used both to create the profile (first time) and to edit it later."""
    user.username, user.first_name = body.username, body.first_name
    user.last_name, user.bio = body.last_name, body.bio
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "That username is taken")
    return user


@router.get("/search", response_model=list[PublicUser])
async def search(
    q: str = Query(min_length=2, max_length=20),
    me: User = Depends(complete_user),
    db: AsyncSession = Depends(get_db),
):
    hit(f"search:{me.id}", 30, 60)  # stops people scraping the user list
    q = q.strip().lower()
    if not re.fullmatch(r"[a-z0-9._]+", q):
        return []
    rows = await db.scalars(
        select(User)
        .where(User.username.startswith(q, autoescape=True), User.id != me.id)  # "_" is escaped
        .order_by(User.username)
        .limit(10)
    )
    return rows.all()
