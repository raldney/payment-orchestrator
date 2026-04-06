from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infra.config import settings

DATABASE_URL = settings.database_url
engine_kwargs = {'echo': False}
if settings.db_pooling:
    engine_kwargs.update({'pool_size': settings.db_pool_size, 'max_overflow': settings.db_max_overflow, 'pool_timeout': settings.db_pool_timeout, 'pool_recycle': settings.db_pool_recycle})
else:
    engine_kwargs['poolclass'] = NullPool
engine = create_async_engine(DATABASE_URL, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False)

async def init_db():
    async with engine.begin():
        pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
