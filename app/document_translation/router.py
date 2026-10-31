from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.db.session import get_db
from app.core.auth import require_auth
from app.core.readiness import require_ready
from app.document_translation.controller import DocumentTranslationController
from app.document_translation.schemas import DocumentTranslationRequest, DocumentTranslationData
from app.schemas.base import ApiResponse
from app.schemas.errors import COMMON_ERRORS

router = APIRouter(dependencies=[Depends(require_auth), Depends(require_ready)])

@router.post(
    "/document",
    response_model=ApiResponse[DocumentTranslationData],
    summary="Translate document",
    description=(
        "Fetch JSON from a URL and preserve its AST structure. Simple nodes use "
        "the text pipeline; complex or brand-matched nodes use one structured LLM "
        "batch with retrieved semantic examples. The batch bypasses per-node cache "
        "reuse, quality scoring, and persistence. Failed segments retain their "
        "original text, so completion does not guarantee every value was translated."
    ),
    response_description="Document translation status",
    operation_id="translate_document",
    responses=COMMON_ERRORS,
)
async def document_endpoint(
    payload: DocumentTranslationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    uuid: Annotated[str | None, Query(description="Optional Brand UUID for translation context")] = None,
    name: Annotated[str | None, Query(description="Optional Domain name to apply rules")] = None,
):
    brand_uuid = payload.brand_uuid or uuid
    ctl = DocumentTranslationController(db)
    result = await ctl.translate_document(payload, brand_uuid=brand_uuid, domain_name=name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return ApiResponse(success=True, data=DocumentTranslationData(**result), error=None)
