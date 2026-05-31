import asyncio
import logging
from sqlalchemy import text
from app.db.session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    async with engine.begin() as conn:
        try:
            logger.info("Adding trust_score...")
            await conn.execute(text("ALTER TABLE translations ADD COLUMN IF NOT EXISTS trust_score FLOAT"))
        except Exception as e:
            logger.error(f"Error adding trust_score: {e}")
            
        try:
            logger.info("Adding complexity_score...")
            await conn.execute(text("ALTER TABLE translations ADD COLUMN IF NOT EXISTS complexity_score FLOAT"))
        except Exception as e:
            logger.error(f"Error adding complexity_score: {e}")
            
        try:
            logger.info("Backfilling trust_score from score...")
            await conn.execute(text("UPDATE translations SET trust_score = score WHERE trust_score IS NULL"))
        except Exception as e:
            logger.error(f"Error backfilling trust_score: {e}")

    logger.info("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
