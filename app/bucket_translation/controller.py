import asyncio
import logging
import uuid
import os
from typing import List, Dict, Any, cast

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session

from app.bucket_translation.schemas import BucketTranslationRequest
from app.bucket_translation.service import S3Service
from app.text_translation.controller import TextTranslationController
from app.text_translation.schemas import TranslationRequest
from app.pipeline import json_to_ast, collect_translatable_nodes, DocumentNode
from app.bucket_translation.models import BucketTranslationOperation, FileTranslationOperation
from app.bucket_translation.repository import BucketTranslationRepository

logger = logging.getLogger(__name__)

class BucketTranslationController:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BucketTranslationRepository(db)

    async def create_bucket_operation(self, payload: BucketTranslationRequest) -> str:
        operation_id = str(uuid.uuid4())
        bucket_op = BucketTranslationOperation(
            id=operation_id,
            bucket_name=payload.bucket_name,
            source_prefix=payload.source_prefix,
            target_prefix=payload.target_prefix,
            source_lang=payload.source_lang,
            target_lang=payload.target_lang,
            status="PENDING",
            total_files=0,
            processed_files=0,
            failed_files=0,
            skipped_files=0
        )
        await self.repo.create_operation(bucket_op)
        return operation_id


async def _try_copy_from_cache(
    s3_service: S3Service,
    repo: BucketTranslationRepository,
    cached_record: Any,
    source_key: str,
    bucket_name: str,
    target_key: str,
    file_id: str,
    operation_id: str,
    file_hash: str,
) -> bool:
    if not cached_record:
        return False

    _, cached_bucket_op = cached_record
    logger.info(f"Skipping {source_key} due to cache hit (hash: {file_hash}).")
    
    if source_key.startswith(cached_bucket_op.source_prefix):
        old_target_key = cached_bucket_op.target_prefix + source_key[len(cached_bucket_op.source_prefix):]
    else:
        old_target_key = cached_bucket_op.target_prefix + source_key
        
    try:
        await asyncio.to_thread(
            s3_service.copy_object,
            cached_bucket_op.bucket_name,
            old_target_key,
            bucket_name,
            target_key
        )
        await repo.update_file_operation(file_id, status="SKIPPED")
        await repo.increment_operation_counter(operation_id, "skipped_files", 1)
        return True
    except Exception as copy_err:
        logger.warning(f"Cache hit but failed to copy {old_target_key} to {target_key} (maybe deleted?). Falling back to translation. Error: {copy_err}")
        return False

async def _translate_segments(
    text_ctl: TextTranslationController,
    translatable_nodes: list,
    source_lang: str,
    target_lang: str,
    brand_uuid: str | None,
    source_key: str,
):
    for node in translatable_nodes:
        seg_payload = TranslationRequest(
            text=node.value,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        try:
            res = await text_ctl.translate_text(
                payload=seg_payload,
                brand_uuid=brand_uuid,
                filename=os.path.basename(source_key),
                property_name=node.path,
            )
            if "error" in res:
                logger.warning("Failed to translate segment in %s: %s", source_key, res["error"])
                node.translated_value = node.value
            else:
                node.translated_value = res.get("translation", node.value)
        except Exception:
            logger.exception("Error translating segment in %s", source_key)
            node.translated_value = node.value

async def process_s3_file(
    s3_service: S3Service,
    operation_id: str,
    file_id: str,
    bucket_name: str,
    source_key: str,
    target_key: str,
    source_lang: str,
    target_lang: str,
    file_hash: str,
    brand_uuid: str | None = None,
):
    status = "FAILED"
    error_message = None
    
    try:
        # Check cache
        async with async_session() as db:
            repo = BucketTranslationRepository(db)
            cached_record = await repo.find_cached_successful_file_operation(
                source_key=source_key, file_hash=file_hash, target_lang=target_lang
            )
            
            copied = await _try_copy_from_cache(
                s3_service, repo, cached_record, source_key, bucket_name, target_key, file_id, operation_id, file_hash
            )
            if copied:
                return

        # If not cached or if cache copy failed, continue with translation
        doc_data = await asyncio.to_thread(s3_service.download_json, bucket_name, source_key)
        
        root_node = json_to_ast(doc_data)
        doc_node = DocumentNode(root_node, "json")
        translatable_nodes = collect_translatable_nodes(doc_node)
        
        async with async_session() as db:
            text_ctl = TextTranslationController(db)
            await _translate_segments(text_ctl, translatable_nodes, source_lang, target_lang, brand_uuid, source_key)

        translated_document = doc_node.to_dict()
        
        await asyncio.to_thread(s3_service.upload_json, bucket_name, target_key, translated_document)
        status = "SUCCESS"

    except Exception as e:
        import traceback
        from botocore.exceptions import ClientError
        logger.exception("Failed to process file %s", source_key)
        error_message = str(e)
        if isinstance(e, ClientError):
            error_message += f"\nResponse: {e.response}"
        error_message += f"\nTraceback: {traceback.format_exc()}"

    # Update the DB for this file
    async with async_session() as db:
        repo = BucketTranslationRepository(db)
        await repo.update_file_operation(file_id, status=status, error_message=error_message)
        # Update bucket operation counts
        counter_field = "processed_files" if status == "SUCCESS" else "failed_files"
        await repo.increment_operation_counter(operation_id, counter_field, 1)


async def background_bucket_translation(operation_id: str, payload: BucketTranslationRequest):
    s3_service = S3Service()
    
    async with async_session() as db:
        repo = BucketTranslationRepository(db)
        await repo.update_operation(operation_id, status="PROCESSING")

    try:
        files = await asyncio.to_thread(
            s3_service.list_json_files, payload.bucket_name, payload.source_prefix
        )
    except Exception:
        async with async_session() as db:
            repo = BucketTranslationRepository(db)
            await repo.update_operation(operation_id, status="FAILED")
        logger.exception("Bucket translation %s failed to list files", operation_id)
        return

    async with async_session() as db:
        repo = BucketTranslationRepository(db)
        await repo.update_operation(operation_id, total_files=len(files))

    tasks = []
    
    for file_obj in files:
        if isinstance(file_obj, str):
            # Fallback if dictionary format is not implemented properly
            key = cast(str, file_obj)
            size = 0
            etag = ""
        else:
            key = cast(str, file_obj['Key'])
            size = cast(int, file_obj['Size'])
            etag = cast(str, file_obj['ETag'])
            
        file_hash = f"{etag}-{size}"
        
        file_id = str(uuid.uuid4())
        file_name = os.path.basename(key)
        extension = os.path.splitext(file_name)[1] if '.' in file_name else None
        
        if key.startswith(payload.source_prefix):
            target_key = payload.target_prefix + key[len(payload.source_prefix):]
        else:
            target_key = payload.target_prefix + key
            
        async with async_session() as db:
            repo = BucketTranslationRepository(db)
            file_op = FileTranslationOperation(
                id=file_id,
                bucket_operation_id=operation_id,
                file_key=key,
                file_name=file_name,
                extension=extension,
                file_size=size,
                etag=etag,
                file_hash=file_hash,
                status="PENDING"
            )
            await repo.create_file_operation(file_op)
            
        tasks.append(
            process_s3_file(
                s3_service=s3_service,
                operation_id=operation_id,
                file_id=file_id,
                bucket_name=payload.bucket_name,
                source_key=key,
                target_key=target_key,
                source_lang=payload.source_lang,
                target_lang=payload.target_lang,
                file_hash=file_hash,
                brand_uuid=payload.brand_uuid
            )
        )

    # Process all files concurrently
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Mark bucket operation as completed
    async with async_session() as db:
        repo = BucketTranslationRepository(db)
        await repo.update_operation(operation_id, status="COMPLETED")
