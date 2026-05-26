"""
Translation API endpoints (v1).

Provides text translation, language detection, and document translation.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.auth import require_auth
from app.controllers.translation_controller import (
    translate_text_controller,
    detect_language_controller,
    translate_document_controller,
)
from app.schemas.translation import (
    ApiResponse,
    TranslationRequest,
    TranslationData,
    DetectionRequest,
    DetectionData,
    DocumentTranslationRequest,
    DocumentTranslationData,
)
from app.schemas.errors import COMMON_ERRORS

router = APIRouter(dependencies=[Depends(require_auth)])


@router.post(
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
async def translate(
    payload: TranslationRequest,
    uuid: str | None = Query(None, description="Optional Brand UUID to inject context"),
    name: str | None = Query(None, description="Optional Domain name to apply rules"),
    db: AsyncSession = Depends(get_db),
):
    """Translate text between supported language pairs."""
    result = await translate_text_controller(payload, db, brand_uuid=uuid, domain_name=name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return ApiResponse(success=True, data=TranslationData(**result), error=None)


@router.post(
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
async def detect(payload: DetectionRequest):
    """Detect the language of the input text."""
    result = await detect_language_controller(payload)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return ApiResponse(success=True, data=DetectionData(**result), error=None)


@router.post(
    "/document",
    response_model=ApiResponse[DocumentTranslationData],
    summary="Translate document",
    description=(
        "Submit a document URL for translation. The document will be fetched, "
        "parsed, and each translatable segment processed through the translation "
        "pipeline.\n\n"
        "> **Note**: This endpoint is a stub and will be fully implemented in a "
        "future release."
    ),
    response_description="Document translation status",
    operation_id="translate_document",
    responses=COMMON_ERRORS,
)
async def document(
    payload: DocumentTranslationRequest,
    uuid: str | None = Query(None, description="Optional Brand UUID to inject context"),
    name: str | None = Query(None, description="Optional Domain name to apply rules"),
):
    """Translate a full document by URL."""
    result = await translate_document_controller(payload, brand_uuid=uuid, domain_name=name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return ApiResponse(success=True, data=DocumentTranslationData(**result), error=None)
