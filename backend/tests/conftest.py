import os
import tempfile
import uuid

os.environ.update(ENV="test", JWT_SECRET="x" * 40,
                  DATABASE_URL=f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/test.db")

import pytest
from fastapi.testclient import TestClient
from app.core import ratelimit
from app.db import mongo
from app.main import app
from tests.fake_mongo import FakeDb


@pytest.fixture()
def client():
    ratelimit._hits.clear()
    mongo.db = FakeDb()
    with TestClient(app) as c:
        yield c


def signup(client, username, first="Test", last=None):
    """Full signup + profile. Returns (headers, access_token, user dict)."""
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    assert client.post("/api/auth/register", json={"email": email}).status_code == 202
    v = client.post("/api/auth/verify-otp", json={"email": email, "code": "123456"})
    assert v.status_code == 200
    t = client.post("/api/auth/set-password", json={"signup_token": v.json()["signup_token"], "password": "pass1234"})
    assert t.status_code == 201
    tok = t.json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    p = client.put("/api/users/me/profile", headers=h, json={"username": username, "first_name": first, "last_name": last})
    assert p.status_code == 200, p.text
    return h, tok, p.json(), email
