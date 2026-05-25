from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db

from app.controllers.translation_controller import (
    translate_text_controller,
    detect_language_controller,
    translate_document_controller
)
from app.schemas.translation import (
    ApiResponse,
    TranslationRequest,
    TranslationData,
    DetectionRequest,
    DetectionData,
    DocumentTranslationRequest,
    DocumentTranslationData
)

router = APIRouter()

@router.post("/translate", response_model=ApiResponse[TranslationData])
async def translate(payload: TranslationRequest, db: AsyncSession = Depends(get_db)):
    """
    Route for text translation.
    """
    result = await translate_text_controller(payload.model_dump(), db)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return ApiResponse(success=True, data=TranslationData(**result), error=None)

@router.post("/detecte", response_model=ApiResponse[DetectionData])
async def detect(payload: DetectionRequest):
    """
    Route for language detection.
    """
    result = await detect_language_controller(payload.model_dump())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return ApiResponse(success=True, data=DetectionData(**result), error=None)

@router.post("/document", response_model=ApiResponse[DocumentTranslationData])
async def document(payload: DocumentTranslationRequest):
    """
    Route for document translation.
    """
    result = await translate_document_controller(payload.model_dump())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return ApiResponse(success=True, data=DocumentTranslationData(**result), error=None)
