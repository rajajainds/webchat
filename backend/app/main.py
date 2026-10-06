# App entry point. Run: uvicorn app.main:app --reload
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import mongo
from app.db.postgres import engine
from app.models.user import Base
from app.routers import auth, conversations, users, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.env != "prod":  # prod uses Alembic migrations instead
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    if settings.env != "test":  # tests do not need MongoDB
        await mongo.init()
    yield
    await mongo.close()
    await engine.dispose()


app = FastAPI(title="Web Chat", lifespan=lifespan, docs_url=None if settings.env == "prod" else "/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(conversations.router)
app.include_router(ws.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
