# Sprint 3: live chat over one WebSocket per device.
# Client sends: auth, send_message, mark_read.
# Server sends: auth_ok, new_message, read_state, error.
import asyncio
import time
import uuid
from collections import deque
from contextlib import suppress
import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from app.config import settings
from app.core.security import read_token
from app.db.postgres import SessionLocal
from app.models.user import User
from app.schemas.chat import SendIn
from app.services import chat
from app.ws.manager import manager

router = APIRouter()


async def _close(ws: WebSocket, code: int) -> None:
    with suppress(Exception):
        await ws.close(code=code)


async def _handle(uid: str, data: dict, sent: deque) -> None:
    kind = data.get("type")
    if kind == "send_message":
        cid = data.get("client_msg_id")
        try:
            now = time.monotonic()  # max 20 messages per 10 seconds per socket
            while sent and now - sent[0] > 10:
                sent.popleft()
            if len(sent) >= 20:
                raise ValueError("You are sending too fast")
            sent.append(now)
            body = SendIn(**{k: data.get(k) for k in ("conversation_id", "client_msg_id", "text")})
            conv = await chat.get_for_member(body.conversation_id, uid)  # sender must be a member
            msg = chat.message_out(await chat.save_message(conv, uid, body.text, body.client_msg_id))
        except ValidationError as e:
            await manager.send_user(uid, {"type": "error", "client_msg_id": cid, "detail": e.errors()[0]["msg"]})
            return
        except (ValueError, LookupError) as e:
            await manager.send_user(uid, {"type": "error", "client_msg_id": cid, "detail": str(e)})
            return
        # Saved. Now push to every open socket of both people (incl. sender's other devices).
        event = {"type": "new_message", "message": msg}
        for person in {conv["user_a"], conv["user_b"]}:
            await manager.send_user(person, event)
    elif kind == "mark_read":
        try:
            conv = await chat.get_for_member(str(data.get("conversation_id")), uid)
        except LookupError:
            return
        await chat.mark_read(conv, uid)
        await manager.send_user(uid, {"type": "read_state", "conversation_id": str(conv["_id"]), "unread": 0})
    else:
        await manager.send_user(uid, {"type": "error", "detail": "Unknown event"})


@router.websocket("/ws")
async def chat_socket(ws: WebSocket):
    origin = ws.headers.get("origin")
    if origin and origin not in settings.origins:  # only our own site may connect
        await ws.close(code=4403)
        return
    await ws.accept()
    # First message must be {"type":"auth","token":"<access token>"} within 10s.
    try:
        first = await asyncio.wait_for(ws.receive_json(), timeout=10)
        payload = read_token(first["token"], "access") if first.get("type") == "auth" else None
        if not payload:
            raise ValueError
        async with SessionLocal() as db:
            user = await db.get(User, uuid.UUID(payload["sub"]))
        if not user or not user.profile_complete:
            raise ValueError
    except Exception:
        await _close(ws, 4401)
        return
    uid, expires = str(user.id), payload["exp"]
    manager.add(uid, ws)
    await ws.send_json({"type": "auth_ok"})
    sent: deque = deque()
    try:
        while True:
            left = expires - time.time()  # token expiry also ends the socket; client refreshes + reconnects
            if left <= 0:
                await _close(ws, 4401)
                break
            try:
                data = await asyncio.wait_for(ws.receive_json(), timeout=left)
            except asyncio.TimeoutError:
                await _close(ws, 4401)
                break
            except (ValueError, KeyError):  # bad JSON or binary frame
                await ws.send_json({"type": "error", "detail": "Invalid message"})
                continue
            if isinstance(data, dict):
                await _handle(uid, data, sent)
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(uid, ws)
