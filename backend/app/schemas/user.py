# Request/response shapes for profile and search.
import uuid
from typing import Annotated
from pydantic import AfterValidator, BaseModel, ConfigDict, field_validator
from app.core.text import check_username, clean_text

Username = Annotated[str, AfterValidator(check_username)]


class ProfileIn(BaseModel):
    username: Username
    first_name: str
    last_name: str | None = None
    bio: str | None = None

    @field_validator("first_name")
    @classmethod
    def _first(cls, v: str) -> str:
        v = clean_text(v)
        if not 1 <= len(v) <= 50:
            raise ValueError("First name must be 1-50 characters")
        return v

    @field_validator("last_name")
    @classmethod
    def _last(cls, v: str | None) -> str | None:
        v = clean_text(v) if v else ""
        if len(v) > 50:
            raise ValueError("Last name must be at most 50 characters")
        return v or None  # empty means no last name

    @field_validator("bio")
    @classmethod
    def _bio(cls, v: str | None) -> str | None:
        v = clean_text(v) if v else ""
        if len(v) > 160:
            raise ValueError("Bio must be at most 160 characters")
        return v or None


class PublicUser(BaseModel):  # what other people may see (never the email)
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    display_name: str
    initials: str


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    username: str | None
    first_name: str | None
    last_name: str | None
    bio: str | None
    initials: str
    display_name: str
    profile_complete: bool
