# Sprint 2: chat list, open a chat, history, mark read.
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.deps import complete_user, get_db
from app.models.user import User
from app.schemas.chat import ConvOut, MessageOut, OpenConvIn
from app.schemas.user import PublicUser
from app.services import chat
from app.ws.manager import manager

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _public(u: User) -> dict:
    return PublicUser.model_validate(u).model_dump(mode="json")


@router.get("", response_model=list[ConvOut])
async def list_chats(me: User = Depends(complete_user), db: AsyncSession = Depends(get_db)):
    convs = await chat.list_for_user(me.id)
    other_ids = {uuid.UUID(c["user_b"] if c["user_a"] == str(me.id) else c["user_a"]) for c in convs}
    users = {}
    if other_ids:
        users = {u.id: u for u in (await db.scalars(select(User).where(User.id.in_(other_ids)))).all()}
    out = []
    for c in convs:  # already sorted: latest message first
        oid = uuid.UUID(c["user_b"] if c["user_a"] == str(me.id) else c["user_a"])
        if oid in users:
            out.append(chat.summary(c, me.id, _public(users[oid])))
    return out


@router.post("", response_model=ConvOut)
async def open_chat(body: OpenConvIn, me: User = Depends(complete_user), db: AsyncSession = Depends(get_db)):
    other = await db.scalar(select(User).where(User.username == body.username))
    if not other:
        raise HTTPException(404, "No user with that username")
    if other.id == me.id:
        raise HTTPException(400, "You cannot chat with yourself")
    conv = await chat.get_or_create(me.id, other.id)
    return chat.summary(conv, me.id, _public(other))


@router.get("/{conv_id}/messages", response_model=list[MessageOut])
async def messages(
    conv_id: str,
    before_seq: int | None = Query(default=None, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
    me: User = Depends(complete_user),
):
    try:
        conv = await chat.get_for_member(conv_id, me.id)
    except LookupError:
        raise HTTPException(404, "Conversation not found")
    return [chat.message_out(m) for m in await chat.history(conv["_id"], before_seq, limit)]


@router.post("/{conv_id}/read", status_code=204)
async def read(conv_id: str, me: User = Depends(complete_user)):
    try:
        conv = await chat.get_for_member(conv_id, me.id)
    except LookupError:
        raise HTTPException(404, "Conversation not found")
    await chat.mark_read(conv, me.id)
    # Tell my other devices so their unread badge clears too.
    await manager.send_user(str(me.id), {"type": "read_state", "conversation_id": conv_id, "unread": 0})
