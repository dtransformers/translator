from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Annotated

from app.db.session import get_db, async_session
from app.core.auth import require_auth
from app.text_translation.controller import TextTranslationController
from app.text_translation.schemas import (
    TranslationRequest,
    TranslationData,
    DetectionRequest,
    DetectionData,
)
from app.schemas.base import ApiResponse
from app.schemas.errors import COMMON_ERRORS

translation_router = APIRouter(dependencies=[Depends(require_auth)])
review_router = APIRouter(prefix="/review", dependencies=[Depends(require_auth)], tags=["review"])
debug_router = APIRouter(prefix="/debug", tags=["debug"])

@translation_router.post(
    "/translate",
    response_model=ApiResponse[TranslationData],
    summary="Translate text",
    description=(
        "Translate a text string from a source language to a target language.\n\n"
        "The pipeline includes:\n"
        "- **Translatability check** — skips emojis, URLs, numbers, HTML\n"
        "- **Multi-tier cache** — exact → normalized → semantic vector lookup\n"
        "- **Complexity routing** — simple texts use MarianMT, complex texts use LLM\n"
        "- **Quality scoring** — cosine-similarity-based quality estimation\n"
        "- **Brand context** — optional brand-specific tone, glossary, audience\n"
        "- **Reusable units** — known entity/phrase translations injected as glossary"
    ),
    response_description="Translated text with metadata",
    operation_id="translate_text",
    responses=COMMON_ERRORS,
)
async def translate_text_endpoint(
    payload: TranslationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    uuid: str | None = Query(None, description="Optional Brand UUID to inject context"),
    name: str | None = Query(None, description="Optional Domain name to apply rules"),
):
    """Translate text between supported language pairs."""
    ctl = TextTranslationController(db)
    result = await ctl.translate_text(payload, brand_uuid=uuid, domain_name=name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return ApiResponse(success=True, data=TranslationData(**result), error=None)


@translation_router.post(
    "/detect",
    response_model=ApiResponse[DetectionData],
    summary="Detect language",
    description=(
        "Detect the language of the provided text using statistical analysis.\n\n"
        "Returns an ISO 639-1 language code (e.g., `en`, `fr`, `ar`, `zh`)."
    ),
    response_description="Detected language code",
    operation_id="detect_language",
    responses=COMMON_ERRORS,
)
async def detect_language_endpoint(payload: DetectionRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """Detect the language of the input text."""
    ctl = TextTranslationController(db)
    result = ctl.detect_language(payload)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return ApiResponse(success=True, data=DetectionData(**result), error=None)



async def _run_review_background():
    async with async_session() as db:
        ctl = TextTranslationController(db)
        try:
            await ctl.run_review()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Background review failed: {e}")

@review_router.post(
    "/start",
    summary="Start translation review",
    description="Runs a background task to scan and fix poorly translated entries.",
    status_code=202,
)
async def start_review(
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(_run_review_background)
    return {
        "success": True,
        "message": "Review batch process started in the background."
    }


@debug_router.get("/check_db")
async def check_db():
    from sqlalchemy import text
    async with async_session() as db:
        result = await db.execute(text("SELECT id, value, translation FROM translations WHERE value LIKE '[%' LIMIT 5;"))
        rows = result.fetchall()
        return [{"id": row[0], "value": row[1], "translation": row[2]} for row in rows]
