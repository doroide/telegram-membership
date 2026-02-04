import asyncio
from dotenv import load_dotenv

load_dotenv()  # loads .env automatically

from backend.app.db.base import Base
from backend.app.db.session import engine
from backend.app.db import models


async def init():
    async with engine.begin() as conn:
        print("⚠️ Dropping old tables...")
        await conn.run_sync(Base.metadata.drop_all)

        print("✅ Creating fresh tables...")
        await conn.run_sync(Base.metadata.create_all)

    print("🚀 Database reset complete")


if __name__ == "__main__":
    asyncio.run(init())
