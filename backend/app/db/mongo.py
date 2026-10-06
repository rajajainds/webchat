# MongoDB connection (PyMongo native async). Opened at startup, closed at shutdown.
from pymongo import AsyncMongoClient
from app.config import settings

client: AsyncMongoClient | None = None
db = None  # AsyncDatabase, set by init()


async def init() -> None:
    global client, db
    client = AsyncMongoClient(settings.mongo_url, tz_aware=True)
    db = client[settings.mongo_db]
    # Indexes: fast lookups + uniqueness rules.
    await db.conversations.create_index("pair_key", unique=True)
    await db.conversations.create_index([("user_a", 1), ("last_message_at", -1)])
    await db.conversations.create_index([("user_b", 1), ("last_message_at", -1)])
    await db.messages.create_index([("conversation_id", 1), ("seq", 1)], unique=True)
    await db.messages.create_index(
        [("conversation_id", 1), ("sender_id", 1), ("client_msg_id", 1)], unique=True
    )


async def close() -> None:
    if client:
        await client.close()
