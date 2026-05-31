import asyncio
from sqlalchemy import text
from app.db.session import async_session

async def check():
    async with async_session() as db:
        result = await db.execute(text("SELECT id, value, translation FROM translations WHERE value LIKE '[%' LIMIT 5;"))
        rows = result.fetchall()
        for row in rows:
            print(row)

if __name__ == "__main__":
    asyncio.run(check())
