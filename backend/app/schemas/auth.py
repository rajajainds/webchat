# Request/response shapes for auth endpoints.
import re
from typing import Annotated
from pydantic import AfterValidator, BaseModel, EmailStr, StringConstraints


def _lower(v: str) -> str:
    return v.strip().lower()


def _password(v: str) -> str:
    if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
        raise ValueError("Password needs at least one letter and one number")
    return v


Email = Annotated[EmailStr, AfterValidator(_lower)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128), AfterValidator(_password)]


class EmailIn(BaseModel):
    email: Email


class VerifyIn(BaseModel):
    email: Email
    code: Annotated[str, StringConstraints(pattern=r"^\d{4,10}$")]


class SetPasswordIn(BaseModel):
    signup_token: str
    password: Password


class LoginIn(BaseModel):
    identifier: Annotated[str, StringConstraints(min_length=3, max_length=254)]  # email or username
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class RefreshIn(BaseModel):
    refresh_token: str


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
