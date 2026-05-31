import asyncio
import logging
import uuid
import os
from typing import List, Dict, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.translation import BucketTranslationRequest, TranslationRequest
from app.services.s3_service import S3Service
from app.db.session import async_session
from app.controllers.translation_controller import translate_text_controller
from app.pipeline import json_to_ast, collect_translatable_nodes, DocumentNode
from app.translations.models import BucketTranslationOperation, FileTranslationOperation

logger = logging.getLogger(__name__)

async def create_bucket_operation(payload: BucketTranslationRequest, db: AsyncSession) -> str:
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
    db.add(bucket_op)
    await db.commit()
    return operation_id

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
    """Process a single JSON file from S3 and update DB incrementally."""
    status = "FAILED"
    error_message = None
    
    try:
        # Check cache
        async with async_session() as db:
            stmt = select(FileTranslationOperation, BucketTranslationOperation).join(
                BucketTranslationOperation,
                FileTranslationOperation.bucket_operation_id == BucketTranslationOperation.id
            ).where(
                FileTranslationOperation.file_key == source_key,
                FileTranslationOperation.file_hash == file_hash,
                FileTranslationOperation.status == "SUCCESS",
                BucketTranslationOperation.target_lang == target_lang
            )
            result = await db.execute(stmt)
            cached_record = result.first()
            
            if cached_record:
                cached_file, cached_bucket_op = cached_record
                logger.info(f"Skipping {source_key} due to cache hit (hash: {file_hash}).")
                
                # We need to copy the object from its old target location to the new one
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
                    
                    # If copy succeeds, update the current file operation to SKIPPED
                    await db.execute(
                        update(FileTranslationOperation)
                        .where(FileTranslationOperation.id == file_id)
                        .values(status="SKIPPED")
                    )
                    await db.commit()
                    # Update bucket operation skipped count
                    await db.execute(
                        update(BucketTranslationOperation)
                        .where(BucketTranslationOperation.id == operation_id)
                        .values(skipped_files=BucketTranslationOperation.skipped_files + 1)
                    )
                    await db.commit()
                    return
                except Exception as copy_err:
                    logger.warning(f"Cache hit but failed to copy {old_target_key} to {target_key} (maybe deleted?). Falling back to translation. Error: {copy_err}")
                    # We just log it and fall through to normal translation process.
                    
        # If not cached or if cache copy failed, continue with translation
        doc_data = await asyncio.to_thread(s3_service.download_json, bucket_name, source_key)
        
        root_node = json_to_ast(doc_data)
        doc_node = DocumentNode(root_node, "json")
        translatable_nodes = collect_translatable_nodes(doc_node)
        
        async with async_session() as db:
            for node in translatable_nodes:
                seg_payload = TranslationRequest(
                    text=node.value,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
                try:
                    res = await translate_text_controller(
                        payload=seg_payload,
                        db=db,
                        brand_uuid=brand_uuid,
                        filename=os.path.basename(source_key),
                        property_name=node.path,
                    )
                    if "error" in res:
                        logger.warning("Failed to translate segment in %s: %s", source_key, res["error"])
                        node.translated_value = node.value
                    else:
                        node.translated_value = res.get("translation", node.value)
                except Exception as e:
                    logger.error("Error translating segment in %s: %s", source_key, e)
                    node.translated_value = node.value

        translated_document = doc_node.to_dict()
        
        await asyncio.to_thread(s3_service.upload_json, bucket_name, target_key, translated_document)
        status = "SUCCESS"

    except Exception as e:
        import traceback
        from botocore.exceptions import ClientError
        logger.error("Failed to process file %s: %s", source_key, e)
        error_message = str(e)
        if isinstance(e, ClientError):
            error_message += f"\nResponse: {e.response}"
        error_message += f"\nTraceback: {traceback.format_exc()}"

    # Update the DB for this file
    async with async_session() as db:
        await db.execute(
            update(FileTranslationOperation)
            .where(FileTranslationOperation.id == file_id)
            .values(status=status, error_message=error_message)
        )
        # Update bucket operation counts
        if status == "SUCCESS":
            await db.execute(
                update(BucketTranslationOperation)
                .where(BucketTranslationOperation.id == operation_id)
                .values(processed_files=BucketTranslationOperation.processed_files + 1)
            )
        else:
            await db.execute(
                update(BucketTranslationOperation)
                .where(BucketTranslationOperation.id == operation_id)
                .values(failed_files=BucketTranslationOperation.failed_files + 1)
            )
        await db.commit()


async def background_bucket_translation(operation_id: str, payload: BucketTranslationRequest):
    s3_service = S3Service()
    
    async with async_session() as db:
        await db.execute(
            update(BucketTranslationOperation)
            .where(BucketTranslationOperation.id == operation_id)
            .values(status="PROCESSING")
        )
        await db.commit()

    try:
        files = await asyncio.to_thread(
            s3_service.list_json_files, payload.bucket_name, payload.source_prefix
        )
    except Exception as e:
        async with async_session() as db:
            await db.execute(
                update(BucketTranslationOperation)
                .where(BucketTranslationOperation.id == operation_id)
                .values(status="FAILED")
            )
            await db.commit()
        logger.error(f"Bucket translation {operation_id} failed to list files: {e}")
        return

    async with async_session() as db:
        await db.execute(
            update(BucketTranslationOperation)
            .where(BucketTranslationOperation.id == operation_id)
            .values(total_files=len(files))
        )
        await db.commit()

    tasks = []
    
    for file_obj in files:
        if isinstance(file_obj, str):
            # Fallback if dictionary format is not implemented properly
            key = file_obj
            size = 0
            etag = ""
        else:
            key = file_obj['Key']
            size = file_obj['Size']
            etag = file_obj['ETag']
            
        file_hash = f"{etag}-{size}"
        
        file_id = str(uuid.uuid4())
        file_name = os.path.basename(key)
        extension = os.path.splitext(file_name)[1] if '.' in file_name else None
        
        if key.startswith(payload.source_prefix):
            target_key = payload.target_prefix + key[len(payload.source_prefix):]
        else:
            target_key = payload.target_prefix + key
            
        async with async_session() as db:
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
            db.add(file_op)
            await db.commit()
            
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
        await db.execute(
            update(BucketTranslationOperation)
            .where(BucketTranslationOperation.id == operation_id)
            .values(status="COMPLETED")
        )
        await db.commit()
