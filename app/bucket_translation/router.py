from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.db.session import get_db
from app.core.auth import require_auth
from app.bucket_translation.controller import BucketTranslationController, background_bucket_translation
from app.bucket_translation.schemas import (
    BucketTranslationRequest,
    BucketOperationStatusResponse,
    FileOperationStatusResponse,
)
from app.schemas.base import ApiResponse
from app.schemas.errors import COMMON_ERRORS

router = APIRouter(dependencies=[Depends(require_auth)])

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
    db: Annotated[AsyncSession, Depends(get_db)]
):
    ctl = BucketTranslationController(db)
    operation_id = await ctl.create_bucket_operation(payload)
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
async def get_bucket_status(operation_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    ctl = BucketTranslationController(db)
    operation = await ctl.repo.get_operation(operation_id)
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
async def get_bucket_files_status(operation_id: str, db: Annotated[AsyncSession, Depends(get_db)]):
    ctl = BucketTranslationController(db)
    files = await ctl.repo.get_file_operations_by_operation_id(operation_id)
    
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
