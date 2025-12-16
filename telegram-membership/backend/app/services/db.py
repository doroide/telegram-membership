from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from ..config import settings
from ..models import Base

# Convert normal DB URL to async URL
# Example:
# postgresql://user:pass@host/db
# becomes:
# postgresql+asyncpg://user:pass@host/db
async_db_url = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)

# Create async engine
engine = create_async_engine(
    async_db_url,
    echo=True,          # shows SQL logs (useful during development)
    future=True
)

# Create session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# Dependency for routes to access DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Initialize database schema (create tables)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
