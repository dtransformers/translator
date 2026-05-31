from fastapi import APIRouter
from sqlalchemy import text
from app.db.session import async_session

router = APIRouter()

@router.get("/check_db")
async def check_db():
    async with async_session() as db:
        result = await db.execute(text("SELECT id, value, translation FROM translations WHERE value LIKE '[%' LIMIT 5;"))
        rows = result.fetchall()
        return [{"id": row[0], "value": row[1], "translation": row[2]} for row in rows]
