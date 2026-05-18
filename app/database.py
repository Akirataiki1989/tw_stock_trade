from sqlalchemy.ext.asyncio.session import AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

engine: AsyncEngine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
