import asyncio

from backend.app.db.base import Base
from backend.app.db.session import engine

# VERY IMPORTANT: this imports all models
# so SQLAlchemy knows what tables to create
from backend.app.db import models


async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✅ All tables created successfully")


if __name__ == "__main__":
    asyncio.run(init())
