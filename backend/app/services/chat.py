# Chat logic on MongoDB. Rule: SAVE first, push over WebSocket second.
# conversations: one doc per pair of users. messages: one doc per message.
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app.db import mongo


def _now() -> datetime:
    return datetime.now(timezone.utc)


def pair_key(a, b) -> tuple[str, str, str]:
    x, y = sorted([str(a), str(b)])  # sorted, so A+B and B+A give the same key
    return x, y, f"{x}:{y}"


def side_of(conv: dict, uid) -> str:
    return "user_a" if conv["user_a"] == str(uid) else "user_b"


async def get_or_create(me, other) -> dict:
    a, b, key = pair_key(me, other)
    doc = {"user_a": a, "user_b": b, "last_seq": 0, "last_text": None, "last_sender": None,
           "last_message_at": _now(), "user_a_read_seq": 0, "user_b_read_seq": 0, "created_at": _now()}
    try:
        await mongo.db.conversations.update_one({"pair_key": key}, {"$setOnInsert": doc}, upsert=True)
    except DuplicateKeyError:
        pass  # two requests raced; the other one created it
    return await mongo.db.conversations.find_one({"pair_key": key})


async def get_for_member(conv_id: str, uid) -> dict:
    """Returns the conversation, or raises LookupError (also if the user is not in it)."""
    try:
        conv = await mongo.db.conversations.find_one({"_id": ObjectId(conv_id)})
    except InvalidId:
        raise LookupError("not found")
    if not conv or str(uid) not in (conv["user_a"], conv["user_b"]):
        raise LookupError("not found")
    return conv


def message_out(m: dict) -> dict:
    return {"id": str(m["_id"]), "conversation_id": str(m["conversation_id"]), "seq": m["seq"],
            "sender_id": m["sender_id"], "client_msg_id": m["client_msg_id"], "text": m["text"],
            "created_at": m["created_at"].isoformat()}


async def save_message(conv: dict, sender, text: str, client_msg_id: str) -> dict:
    sender = str(sender)
    # Same client_msg_id again (retry after reconnect)? Return the saved one.
    dup = await mongo.db.messages.find_one(
        {"conversation_id": conv["_id"], "sender_id": sender, "client_msg_id": client_msg_id})
    if dup:
        return dup
    now = _now()
    # Atomic counter: gives every message the next seq in this conversation.
    updated = await mongo.db.conversations.find_one_and_update(
        {"_id": conv["_id"]},
        {"$inc": {"last_seq": 1}, "$set": {"last_text": text[:200], "last_sender": sender, "last_message_at": now}},
        return_document=ReturnDocument.AFTER)
    msg = {"conversation_id": conv["_id"], "seq": updated["last_seq"], "sender_id": sender,
           "client_msg_id": client_msg_id, "text": text, "created_at": now}
    res = await mongo.db.messages.insert_one(msg)
    msg["_id"] = res.inserted_id
    # The sender has obviously read up to their own message.
    await mongo.db.conversations.update_one(
        {"_id": conv["_id"]}, {"$max": {f"{side_of(conv, sender)}_read_seq": msg["seq"]}})
    return msg


async def history(conv_id, before_seq: int | None, limit: int) -> list[dict]:
    q = {"conversation_id": conv_id}
    if before_seq:
        q["seq"] = {"$lt": before_seq}
    cur = mongo.db.messages.find(q).sort("seq", -1).limit(limit)
    rows = await cur.to_list(length=limit)
    rows.reverse()  # oldest first, for display
    return rows


async def mark_read(conv: dict, uid) -> None:
    fresh = await mongo.db.conversations.find_one({"_id": conv["_id"]}, {"last_seq": 1})
    await mongo.db.conversations.update_one(
        {"_id": conv["_id"]}, {"$max": {f"{side_of(conv, uid)}_read_seq": fresh["last_seq"]}})


async def list_for_user(uid, limit: int = 100) -> list[dict]:
    uid = str(uid)
    cur = mongo.db.conversations.find(
        {"$or": [{"user_a": uid}, {"user_b": uid}], "last_seq": {"$gt": 0}}  # hide empty chats
    ).sort("last_message_at", -1).limit(limit)
    return await cur.to_list(length=limit)


def summary(conv: dict, me, other_user) -> dict:
    side = side_of(conv, me)
    return {"id": str(conv["_id"]), "other": other_user, "last_text": conv["last_text"],
            "last_sender_id": conv["last_sender"], "last_message_at": conv["last_message_at"].isoformat(),
            "unread": max(0, conv["last_seq"] - conv[f"{side}_read_seq"])}
