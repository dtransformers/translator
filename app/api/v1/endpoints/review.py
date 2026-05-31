from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.session import get_db
from app.core.auth import require_auth
from app.pipeline.reviewer import review_translations_batch

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_auth)])

async def _run_review_background():
    # We create a new DB session for the background task to avoid closed session errors
    from app.db.session import async_session
    async with async_session() as db:
        try:
            await review_translations_batch(db)
        except Exception as e:
            logger.error(f"Background review failed: {e}")

@router.post(
    "/start",
    summary="Start translation review",
    description="Runs a background task to scan and fix poorly translated entries.",
    status_code=202,
)
async def start_review(
    background_tasks: BackgroundTasks,
):
    """Trigger the review batch job in the background."""
    background_tasks.add_task(_run_review_background)
    return {
        "success": True,
        "message": "Review batch process started in the background."
    }
