# Web Chat

A real-time, one-to-one chat application with verified email accounts. Python (FastAPI) backend, React frontend, PostgreSQL for accounts, MongoDB for messages, WebSockets for live delivery, and email OTP verification (sent over SMTP, or through Twilio Verify).

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.142-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-8-47A248?logo=mongodb&logoColor=white)

<!-- Add screenshots here: docs/screenshots/chat.png, login.png -->

## Features

- **Verified accounts:** register with an email, receive a one-time code by email, then set a password. No account exists until the email is verified.
- **Profiles:** username (always lowercase), first name, optional last name, bio. No photos: the avatar shows initials (`RJ`, or `R` with no last name).
- **Find people:** search by username prefix, then open a one-to-one chat.
- **Real-time messaging:** text and emoji over WebSockets. English, Hindi (Devanagari) and emoji can be mixed in one message.
- **Nothing is lost:** every message is saved to MongoDB *before* it is delivered. Offline users, and users logging in on a new device, see the full history and unread counts.
- **Multi-device:** the same account can be open on several devices. New messages and "read" state update on all of them live.
- **Chat list:** newest conversation on top, last message preview, unread badge.
- **Security:** argon2id password hashing, short-lived JWT access tokens, rotating single-use refresh tokens, rate limits, token-authenticated WebSockets, strict input validation.

## Architecture

```mermaid
flowchart TD
    B[Browser - React] -->|REST /api| A[FastAPI backend]
    B -->|WebSocket /ws| A
    A --> P[(PostgreSQL<br/>users, refresh tokens)]
    A --> M[(MongoDB<br/>conversations, messages)]
    A --> T[Email provider<br/>SMTP or Twilio Verify]
```

![Architecture](docs/architecture.png)

**Key design decisions**

| Decision | Why |
|---|---|
| Persist first, push second | A message is saved before any delivery attempt, so an offline receiver loses nothing and no push notifications are needed. |
| PostgreSQL for users, MongoDB for chat | Accounts need unique constraints and relations. Messages are an append-only stream read by conversation and order. A chat write never needs a cross-database transaction. |
| Per-conversation `seq` number | An atomic `$inc` gives every message the next number. It defines display order and makes `unread = last_seq - my_read_seq`. |
| `client_msg_id` idempotency | The browser tags each message with a random id. A retry after a dropped connection returns the saved message instead of creating a duplicate. |
| One conversation per pair | `pair_key` (the two user ids, sorted) has a unique index, so two users can never end up with two rooms. |
| Many sockets per user | The connection manager keeps a set per user, so phone and laptop both receive messages and read-state changes. |

<details>
<summary>Sending a message (sequence diagram)</summary>

![Send message sequence](docs/seq_send.png)

</details>

<details>
<summary>Logging in on a second device</summary>

![Second device sequence](docs/seq_second_device.png)

</details>

<details>
<summary>Data model</summary>

![Data model](docs/datamodel.png)

</details>

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2 (async) + asyncpg, PyMongo (native async), PyJWT, pwdlib (argon2id) |
| Frontend | React 19, Vite, React Router, emoji-picker-react |
| Data | PostgreSQL 17, MongoDB 8 (run locally with Docker Compose) |
| Auth / OTP | JWT access + rotating refresh tokens, email OTP (own implementation over SMTP, or Twilio Verify) |
| Tests | pytest, FastAPI TestClient |

Exact versions are pinned in `backend/requirements.txt` and `frontend/package.json`.

## Quick start

**Prerequisites:** Python 3.12, Node.js 22 LTS, Docker Desktop (running), Git.

```bash
# 1. Databases (PostgreSQL + MongoDB in Docker)
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env               # Windows: copy .env.example .env
pytest                             # run the tests
uvicorn app.main:app --reload      # http://localhost:8000/docs

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

Only the two databases run in Docker. The backend and the Vite dev server run directly on your machine.

**Development OTP:** with the SMTP and Twilio variables left empty, no email is sent. The verification code is always `123456` and is printed in the backend log. To receive real codes, fill the `SMTP_*` values (any SMTP server) or the `TWILIO_*` values in `backend/.env`.

### Try it

1. Sign up with any email, enter `123456`, set a password, create a profile.
2. Open a private window and sign up a second user.
3. Search for the first username and start chatting. Send `Hello नमस्ते 😊`.
4. Close one window, send messages from the other, then log back in: unread counts and full history are there.

### Troubleshooting

- **`password authentication failed for user "webchat"`:** another PostgreSQL probably owns port 5432. Change `"5432:5432"` to `"5433:5432"` in `docker-compose.yml`, set the port to `5433` in `DATABASE_URL`, then `docker compose up -d`. If the volume has stale credentials, run `docker compose down -v` first (this deletes local data).
- **`429 Too many requests`:** rate limits are in memory. Use another email or restart the backend.
- **403 "Complete your profile first":** search and chat need a username.

## Configuration

Settings are environment variables in `backend/.env` (see `backend/.env.example`).

| Variable | Meaning |
|---|---|
| `ENV` | `dev` for local use |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:port/dbname` |
| `MONGO_URL`, `MONGO_DB` | MongoDB connection string and database name |
| `JWT_SECRET` | Secret used to sign tokens |
| `ALLOWED_ORIGINS` | Frontend origin, e.g. `http://localhost:5173` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Any SMTP server, used to email the OTP (optional locally) |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_VERIFY_SID` | Alternative: Twilio Verify (optional locally) |
| `OTP_PROVIDER` | `auto` (default), `email`, `twilio` or `dev` |

## API

All REST endpoints are under `/api`. Interactive docs at `/docs`.

| Method and path | Auth | Purpose |
|---|---|---|
| `POST /auth/register` | none | Send email OTP |
| `POST /auth/verify-otp` | none | Check code, returns a short-lived signup token |
| `POST /auth/set-password` | none | Create the account, returns tokens |
| `POST /auth/login` | none | Email or username + password |
| `POST /auth/refresh` | none | Rotate the refresh token |
| `POST /auth/logout` | none | Revoke the refresh token |
| `GET /users/me` | Bearer | Own profile |
| `PUT /users/me/profile` | Bearer | Create or edit profile |
| `GET /users/search?q=` | Bearer + profile | Username prefix search (max 10) |
| `GET /conversations` | Bearer + profile | Chat list, newest first, with unread |
| `POST /conversations` | Bearer + profile | Open (or get) the chat with a username |
| `GET /conversations/{id}/messages` | Bearer + profile | History, paginated by `before_seq` |
| `POST /conversations/{id}/read` | Bearer + profile | Mark read |
| `GET /health` | none | Health check |

**WebSocket (`/ws`):** the first message must be `{"type":"auth","token":"<access token>"}`.

| Direction | Event |
|---|---|
| client to server | `auth`, `send_message {conversation_id, client_msg_id, text}`, `mark_read {conversation_id}` |
| server to client | `auth_ok`, `new_message {message}`, `read_state {conversation_id, unread}`, `error {detail, client_msg_id?}` |

## Project structure

```
webchat/
├── backend/
│   ├── app/
│   │   ├── main.py            # app entry point
│   │   ├── config.py          # settings from env
│   │   ├── deps.py            # DB session, current user
│   │   ├── core/              # security (argon2, JWT), rate limiter, text rules
│   │   ├── db/                # PostgreSQL and MongoDB connections
│   │   ├── models/            # SQLAlchemy tables
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── services/          # otp (Twilio), auth (tokens), chat (MongoDB logic)
│   │   ├── routers/           # auth, users, conversations, ws
│   │   └── ws/manager.py      # open WebSocket connections per user
│   └── tests/
├── frontend/src/              # pages, components, api.js, useChatSocket.js
├── docs/                      # diagrams
└── docker-compose.yml         # local PostgreSQL and MongoDB
```

## Tests

```bash
cd backend && pytest
```

The suite covers the signup and OTP flow, profile rules, login, refresh-token rotation, search, live chat with Hindi and emoji, multi-device delivery, offline messages, duplicate-send protection, and WebSocket auth.

## Author

Built by Raja Jain.
