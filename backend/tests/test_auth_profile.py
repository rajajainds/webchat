import uuid
from tests.conftest import signup


def test_full_signup_profile_login_refresh(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    assert client.post("/api/auth/register", json={"email": email}).status_code == 202
    # wrong OTP is rejected
    assert client.post("/api/auth/verify-otp", json={"email": email, "code": "000000"}).status_code == 400
    v = client.post("/api/auth/verify-otp", json={"email": email.upper(), "code": "123456"}).json()
    # weak password rejected
    assert client.post("/api/auth/set-password", json={"signup_token": v["signup_token"], "password": "short"}).status_code == 422
    assert client.post("/api/auth/set-password", json={"signup_token": v["signup_token"], "password": "onlyletters"}).status_code == 422
    t = client.post("/api/auth/set-password", json={"signup_token": v["signup_token"], "password": "pass1234"}).json()
    h = {"Authorization": f"Bearer {t['access_token']}"}

    me = client.get("/api/users/me", headers=h).json()
    assert me["email"] == email and me["profile_complete"] is False and me["initials"] == "?"
    assert client.get("/api/users/search?q=ab", headers=h).status_code == 403  # profile first

    p = client.put("/api/users/me/profile", headers=h, json={"username": "Raja_K", "first_name": "Raja", "last_name": "Kumar"}).json()
    assert p["username"] == "raja_k" and p["initials"] == "RK" and p["profile_complete"] is True
    p = client.put("/api/users/me/profile", headers=h, json={"username": "raja_k", "first_name": "Raja", "last_name": ""}).json()
    assert p["initials"] == "R" and p["last_name"] is None  # no last name -> one initial

    # login by email and by username, case-insensitive
    assert client.post("/api/auth/login", json={"identifier": email.upper(), "password": "pass1234"}).status_code == 200
    login = client.post("/api/auth/login", json={"identifier": "RAJA_K", "password": "pass1234"})
    assert login.status_code == 200
    assert client.post("/api/auth/login", json={"identifier": "raja_k", "password": "wrong1234"}).status_code == 401
    assert client.post("/api/auth/login", json={"identifier": "nobody_x", "password": "pass1234"}).status_code == 401

    # refresh rotates: old token stops working
    r1 = login.json()["refresh_token"]
    r2 = client.post("/api/auth/refresh", json={"refresh_token": r1})
    assert r2.status_code == 200
    assert client.post("/api/auth/refresh", json={"refresh_token": r1}).status_code == 401
    assert client.post("/api/auth/logout", json={"refresh_token": r2.json()["refresh_token"]}).status_code == 204
    assert client.post("/api/auth/refresh", json={"refresh_token": r2.json()["refresh_token"]}).status_code == 401


def test_duplicate_username_and_search(client):
    h1, *_ = signup(client, "anita.s", "Anita", "Sharma")
    h2, *_ = signup(client, "anil_k", "Anil")
    dup = client.put("/api/users/me/profile", headers=h2, json={"username": "ANITA.S", "first_name": "Anil"})
    assert dup.status_code == 409
    res = client.get("/api/users/search?q=ani", headers=h2).json()
    assert [u["username"] for u in res] == ["anita.s"]  # self excluded
    assert "email" not in res[0] and res[0]["initials"] == "AS"
    assert client.get("/api/users/search?q=a_", headers=h2).json() == []  # "_" is not a wildcard
    assert client.get("/api/users/search?q=ani").status_code == 401


def test_set_password_twice_and_bad_token(client):
    assert client.post("/api/auth/set-password", json={"signup_token": "junk", "password": "pass1234"}).status_code == 400
    _, tok, _, email = signup(client, "dupuser1")
    v = client.post("/api/auth/verify-otp", json={"email": email, "code": "123456"}).json()
    assert client.post("/api/auth/set-password", json={"signup_token": v["signup_token"], "password": "pass1234"}).status_code == 409
    # an access token must not work as a signup token
    assert client.post("/api/auth/set-password", json={"signup_token": tok, "password": "pass1234"}).status_code == 400


def test_register_does_not_reveal_existing_email(client):
    _, _, _, email = signup(client, "existing1")
    r = client.post("/api/auth/register", json={"email": email})
    assert r.status_code == 202 and "If this email" in r.json()["message"]


def test_otp_rate_limit(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    codes = [client.post("/api/auth/register", json={"email": email}).status_code for _ in range(4)]
    assert codes == [202, 202, 202, 429]
