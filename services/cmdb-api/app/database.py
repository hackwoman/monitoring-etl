import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/cmdb"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        # Tables are created by init_db.py script, just verify connection
        await conn.execute(Base.metadata.select().limit(0).select_from(Base.metadata.tables.get("entity_type_def", Base.metadata.tables.get("entity"))))


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
