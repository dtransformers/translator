import asyncio
import logging
from typing import List, Dict, Any

from app.schemas.translation import BucketTranslationRequest, TranslationRequest
from app.services.s3_service import S3Service
from app.db.session import async_session
from app.controllers.translation_controller import translate_text_controller
from app.pipeline import json_to_ast, collect_translatable_nodes, DocumentNode

logger = logging.getLogger(__name__)

async def process_s3_file(
    s3_service: S3Service,
    bucket_name: str,
    source_key: str,
    target_key: str,
    source_lang: str,
    target_lang: str,
) -> dict:
    """Process a single JSON file from S3."""
    status = {"file": source_key, "status": "failed", "target_key": target_key, "error": None}
    
    try:
        # Download and parse JSON (offloaded to thread pool)
        doc_data = await asyncio.to_thread(s3_service.download_json, bucket_name, source_key)
        
        # Parse to AST
        root_node = json_to_ast(doc_data)
        doc_node = DocumentNode(root_node, "json")
        translatable_nodes = collect_translatable_nodes(doc_node)
        
        # Translate nodes
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
                        filename=source_key.split('/')[-1],
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

        # Reconstitute document
        translated_document = doc_node.to_dict()
        
        # Upload back to S3 (offloaded to thread pool)
        await asyncio.to_thread(s3_service.upload_json, bucket_name, target_key, translated_document)
        
        status["status"] = "success"
    except Exception as e:
        logger.error("Failed to process file %s: %s", source_key, e)
        status["error"] = str(e)
        
    return status

async def translate_bucket_controller(payload: BucketTranslationRequest) -> dict:
    """Orchestrate translation of all JSON files in a bucket prefix."""
    s3_service = S3Service()
    
    try:
        keys = await asyncio.to_thread(
            s3_service.list_json_files, payload.bucket_name, payload.source_prefix
        )
    except Exception as e:
        return {"error": f"Failed to list files in bucket: {str(e)}"}

    if not keys:
        return {
            "message": "No JSON files found in the specified prefix.",
            "processed_files": 0,
            "failed_files": 0,
            "details": []
        }

    tasks = []
    for key in keys:
        # Determine target key by replacing source_prefix with target_prefix
        if key.startswith(payload.source_prefix):
            target_key = payload.target_prefix + key[len(payload.source_prefix):]
        else:
            target_key = payload.target_prefix + key
            
        tasks.append(
            process_s3_file(
                s3_service=s3_service,
                bucket_name=payload.bucket_name,
                source_key=key,
                target_key=target_key,
                source_lang=payload.source_lang,
                target_lang=payload.target_lang,
            )
        )

    # Process all files concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    details = []
    processed_count = 0
    failed_count = 0
    
    for res in results:
        if isinstance(res, dict):
            details.append(res)
            if res.get("status") == "success":
                processed_count += 1
            else:
                failed_count += 1
        else:
            details.append({"status": "failed", "error": str(res)})
            failed_count += 1

    return {
        "message": "Bucket translation completed.",
        "processed_files": processed_count,
        "failed_files": failed_count,
        "details": details
    }
