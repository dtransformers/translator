from app.schemas.translation import FileOperationStatusResponse
from app.schemas.translation import BucketOperationStatusResponse
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
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
    BucketTranslationRequest,
    BucketTranslationData,
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
    db: AsyncSession = Depends(get_db),
):
    """Translate a full document by URL."""
    result = await translate_document_controller(payload, db, brand_uuid=uuid, domain_name=name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return ApiResponse(success=True, data=DocumentTranslationData(**result), error=None)


@router.post(
    "/bucket",
    response_model=ApiResponse[dict],
    summary="Translate S3/MinIO Bucket path",
    description=(
        "Start an asynchronous background task to translate JSON files in an S3/MinIO bucket. "
        "Returns an operation_id to poll for status."
    ),
    response_description="Bucket translation operation ID",
    operation_id="start_translate_bucket",
    responses=COMMON_ERRORS,
)
async def start_bucket_translation(
    payload: BucketTranslationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    from app.controllers.s3_controller import create_bucket_operation, background_bucket_translation
    operation_id = await create_bucket_operation(payload, db)
    background_tasks.add_task(background_bucket_translation, operation_id, payload)
    return ApiResponse(success=True, data={"operation_id": operation_id}, error=None)

@router.get(
    "/bucket/{operation_id}",
    response_model=ApiResponse[BucketOperationStatusResponse],
    summary="Get bucket translation status",
    description="Retrieve the current status and file counts for a bucket translation operation.",
    operation_id="get_bucket_status",
    responses=COMMON_ERRORS,
)
async def get_bucket_status(operation_id: str, db: AsyncSession = Depends(get_db)):
    from app.translations.models import BucketTranslationOperation
    from sqlalchemy import select
    stmt = select(BucketTranslationOperation).where(BucketTranslationOperation.id == operation_id)
    result = await db.execute(stmt)
    operation = result.scalars().first()
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    return ApiResponse(success=True, data=BucketOperationStatusResponse(
        id=operation.id,
        bucket_name=operation.bucket_name,
        source_prefix=operation.source_prefix,
        target_prefix=operation.target_prefix,
        source_lang=operation.source_lang,
        target_lang=operation.target_lang,
        status=operation.status,
        total_files=operation.total_files,
        processed_files=operation.processed_files,
        failed_files=operation.failed_files,
        skipped_files=operation.skipped_files
    ), error=None)

@router.get(
    "/bucket/{operation_id}/files",
    response_model=ApiResponse[list[FileOperationStatusResponse]],
    summary="Get bucket translation files status",
    description="Retrieve the status of each individual file within a bucket translation operation.",
    operation_id="get_bucket_files_status",
    responses=COMMON_ERRORS,
)
async def get_bucket_files_status(operation_id: str, db: AsyncSession = Depends(get_db)):
    from app.translations.models import FileTranslationOperation
    from sqlalchemy import select
    stmt = select(FileTranslationOperation).where(FileTranslationOperation.bucket_operation_id == operation_id)
    result = await db.execute(stmt)
    files = result.scalars().all()
    
    return ApiResponse(success=True, data=[
        FileOperationStatusResponse(
            id=f.id,
            file_key=f.file_key,
            file_name=f.file_name,
            extension=f.extension,
            tag=f.tag,
            status=f.status,
            file_size=f.file_size,
            etag=f.etag,
            total_chars=f.total_chars,
            error_message=f.error_message
        ) for f in files
    ], error=None)
