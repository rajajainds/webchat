import uuid
import pytest
from app.routers import auth as auth_router
from app.services import otp as otp_module
from app.services.otp import EmailOtp


@pytest.fixture()
def mailbox(client, monkeypatch):
    """Use our own EmailOtp with a fake mail sender that records (to, code)."""
    sent = []

    async def fake_send(to, code):
        sent.append((to, code))

    monkeypatch.setattr(auth_router, "otp", EmailOtp(sender=fake_send))
    return sent


def new_email():
    return f"{uuid.uuid4().hex[:8]}@example.com"


def verify(client, email, code):
    return client.post("/api/auth/verify-otp", json={"email": email, "code": code})


def test_full_signup_with_our_own_otp(client, mailbox):
    email = new_email()
    assert client.post("/api/auth/register", json={"email": email}).status_code == 202
    to, code = mailbox[0]
    assert to == email and len(code) == 6 and code.isdigit()
    assert verify(client, email, "000000").status_code == 400  # wrong code
    ok = verify(client, email, code)
    assert ok.status_code == 200
    t = client.post("/api/auth/set-password", json={"signup_token": ok.json()["signup_token"], "password": "pass1234"})
    assert t.status_code == 201


def test_code_is_single_use(client, mailbox):
    email = new_email()
    client.post("/api/auth/register", json={"email": email})
    code = mailbox[0][1]
    assert verify(client, email, code).status_code == 200
    assert verify(client, email, code).status_code == 400  # already used


def test_locks_after_five_wrong_tries(client, mailbox):
    email = new_email()
    client.post("/api/auth/register", json={"email": email})
    code = mailbox[0][1]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert verify(client, email, wrong).status_code == 400
    assert verify(client, email, code).status_code == 400  # even the right code is refused now


def test_code_expires(client, mailbox, monkeypatch):
    from datetime import timedelta
    email = new_email()
    client.post("/api/auth/register", json={"email": email})
    code = mailbox[0][1]
    real_now = otp_module._now
    monkeypatch.setattr(otp_module, "_now", lambda: real_now() + timedelta(minutes=11))
    assert verify(client, email, code).status_code == 400


def test_cooldown_between_codes(client, mailbox):
    email = new_email()
    assert client.post("/api/auth/register", json={"email": email}).status_code == 202
    assert client.post("/api/auth/register", json={"email": email}).status_code == 429
    assert len(mailbox) == 1


def test_mail_failure_is_clean_and_retryable(client, monkeypatch):
    calls = []

    async def broken(to, code):
        calls.append(to)
        raise ConnectionError("smtp down")

    monkeypatch.setattr(auth_router, "otp", EmailOtp(sender=broken))
    email = new_email()
    assert client.post("/api/auth/register", json={"email": email}).status_code == 503
    assert client.post("/api/auth/register", json={"email": email}).status_code == 503  # no cooldown lock after a failure
    assert len(calls) == 2
