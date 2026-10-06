# PostgreSQL tables: users and refresh_tokens.
import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from app.core.text import display_name, initials


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(20), unique=True)  # set when profile is created
    first_name: Mapped[str | None] = mapped_column(String(50))
    last_name: Mapped[str | None] = mapped_column(String(50))
    bio: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # DB-level guarantee: usernames and emails are always lowercase.
        CheckConstraint("username = lower(username)", name="ck_username_lower"),
        CheckConstraint("email = lower(email)", name="ck_email_lower"),
        # Makes "username starts with abc" searches use an index.
        Index("ix_users_username_prefix", "username", postgresql_ops={"username": "text_pattern_ops"}),
    )

    @property
    def profile_complete(self) -> bool:
        return bool(self.username and self.first_name)

    @property
    def initials(self) -> str:
        return initials(self.first_name, self.last_name)

    @property
    def display_name(self) -> str:
        return display_name(self.first_name, self.last_name)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256, never the raw token
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
