from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_db():
    async with async_session() as session:
        yield session

async def init_db():

    import logging
    from app.db.base import Base
    from sqlalchemy import text
    logger = logging.getLogger(__name__)

    try:
        # Ping the database to ensure connection is valid
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("Database connection established successfully.")

            # Create tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables verified/created.")
    except Exception as e:
        logger.error(f"Failed to connect to the database or create tables: {e}")
        raise e
