# Request/response shapes for chat.
from pydantic import BaseModel, Field, field_validator
from app.core.text import MAX_MSG, clean_text
from app.schemas.user import PublicUser, Username


class OpenConvIn(BaseModel):
    username: Username


class SendIn(BaseModel):  # WebSocket "send_message" payload
    conversation_id: str
    client_msg_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    text: str

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        v = clean_text(v)
        if not v:
            raise ValueError("Message is empty")
        if len(v) > MAX_MSG:  # counted in characters, so Hindi/emoji get a fair limit
            raise ValueError(f"Message is longer than {MAX_MSG} characters")
        return v


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    seq: int
    sender_id: str
    client_msg_id: str
    text: str
    created_at: str


class ConvOut(BaseModel):
    id: str
    other: PublicUser
    last_text: str | None
    last_sender_id: str | None
    last_message_at: str
    unread: int
