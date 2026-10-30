# Run ONCE on a new database (prod skips create_all at startup):
#   docker compose -f deploy/docker-compose.prod.yml run --rm backend python -m app.create_tables
# It only creates tables that are missing. Changing existing tables later needs Alembic migrations.
import asyncio
from app.db.postgres import engine
from app.models.user import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("tables ready")


if __name__ == "__main__":
    asyncio.run(main())
