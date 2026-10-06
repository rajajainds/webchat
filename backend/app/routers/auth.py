# Sprint 1: register (email + OTP + password), login, refresh, logout.
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.ratelimit import client_ip, hit
from app.core.security import DUMMY_HASH, hash_password, make_token, read_token, verify_password
from app.deps import get_db
from app.models.user import User
from app.schemas.auth import EmailIn, LoginIn, RefreshIn, SetPasswordIn, TokensOut, VerifyIn
from app.services import auth as tokens
from app.services.otp import otp

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=202)
async def register(body: EmailIn, request: Request, db: AsyncSession = Depends(get_db)):
    hit(f"reg-ip:{client_ip(request)}", 10, 3600)
    hit(f"reg-email:{body.email}", 3, 3600)
    taken = await db.scalar(select(User.id).where(User.email == body.email))
    if not taken:
        await otp.send(body.email)
    # Same answer either way, so nobody can test which emails are registered.
    return {"message": "If this email can be registered, a code has been sent."}


@router.post("/verify-otp")
async def verify_otp(body: VerifyIn, request: Request):
    hit(f"verify-ip:{client_ip(request)}", 20, 600)
    hit(f"verify-email:{body.email}", 8, 600)
    if not await otp.check(body.email, body.code):
        raise HTTPException(400, "Invalid or expired code")
    # Short-lived proof that this email was verified.
    return {"signup_token": make_token(body.email, "signup", settings.signup_minutes)}


@router.post("/set-password", response_model=TokensOut, status_code=201)
async def set_password(body: SetPasswordIn, db: AsyncSession = Depends(get_db)):
    try:
        email = read_token(body.signup_token, "signup")["sub"]
    except jwt.PyJWTError:
        raise HTTPException(400, "Verification expired. Start again.")
    user = User(email=email, password_hash=await hash_password(body.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "This email is already registered")
    return await tokens.issue_tokens(db, user)


@router.post("/login", response_model=TokensOut)
async def login(body: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    ident = body.identifier.strip().lower()
    hit(f"login-ip:{client_ip(request)}", 20, 300)
    hit(f"login-id:{ident}", 8, 300)
    user = await db.scalar(select(User).where(or_(User.email == ident, User.username == ident)))
    # Always hash-compare, even for unknown users, so timing does not leak anything.
    ok = await verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok:
        raise HTTPException(401, "Wrong email/username or password")
    return await tokens.issue_tokens(db, user)


@router.post("/refresh", response_model=TokensOut)
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_db)):
    return await tokens.rotate_refresh(db, body.refresh_token)


@router.post("/logout", status_code=204)
async def logout(body: RefreshIn, db: AsyncSession = Depends(get_db)):
    await tokens.revoke_refresh(db, body.refresh_token)
