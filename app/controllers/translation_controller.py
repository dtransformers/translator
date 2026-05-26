"""
Translation controller — thin orchestrator that delegates to entity services.

No direct repository access. All DB operations go through:
    - TranslationService (translations entity)
    - BrandService (brands entity)
"""

import time
import logging
import os
from urllib.parse import urlparse
import httpx

from sqlalchemy.ext.asyncio import AsyncSession

from app.translations.service import TranslationService
from app.brands.service import BrandService
from app.domains.service import DomainService
from app.pipeline import (
    is_translatable,
    is_source_target_compatible,
    is_in_supported_languages,
    calculate_complexity_score,
    translate,
    score_translation,
    json_to_ast,
    collect_translatable_nodes,
    DocumentNode,
)
from app.schemas.translation import (
    TranslationRequest,
    DetectionRequest,
    DocumentTranslationRequest,
)

logger = logging.getLogger(__name__)


async def translate_text_controller(
    payload: TranslationRequest,
    db: AsyncSession,
    brand_uuid: str | None = None,
    domain_name: str | None = None,
    filename: str | None = None,
    property_name: str | None = None,
) -> dict:
    """
    Orchestrate the full translation pipeline:
    verify → cache check → complexity → translate → quality score → persist.
    """
    source_lang = payload.source_lang
    target_lang = payload.target_lang
    text = payload.text

    translation_svc = TranslationService(db)
    brand_svc = BrandService(db)
    domain_svc = DomainService(db)

    start_time = time.time()

    # --- Step 1: Translatability check ---
    if not is_translatable(text):
        translation_time = time.time() - start_time
        await translation_svc.create(
            value=text,
            language=source_lang,
            translation=text,
            translation_language=target_lang,
            is_successed=True,
            notes="Skipped: Input is not translatable (emoji/link/number/HTML)",
            translation_time=translation_time,
            input_size=len(text),
            output_size=len(text),
            filename=filename,
            property=property_name,
        )
        return {
            "message": "Translation skipped: Input is not translatable (emoji/link/number/HTML)",
            "translation": text,
            "skipped": True,
            "reason": "not_translatable",
        }

    # --- Step 2: Language compatibility ---
    compat = is_source_target_compatible(text, source_lang)
    detected_input_lang = compat["detected_lang"]

    if not is_in_supported_languages(source_lang, target_lang):
        return {"error": f"Language pair {source_lang}->{target_lang} is not supported"}

    # --- Step 3: Cache lookup ---
    cached = await translation_svc.find_cached(text, source_lang, target_lang)
    if cached:
        return {
            "message": "Translation retrieved from cache",
            "translation": cached.translation,
            "cached": True,
            "score": cached.score,
        }

    # --- Step 4: Brand context ---
    brand_context = await brand_svc.get_brand_context(brand_uuid)

    # Merge reusable units into the brand glossary
    unit_glossary = await translation_svc.build_glossary_from_units(text, target_lang)
    if unit_glossary:
        existing_glossary = brand_context.get("glossary", {})
        existing_glossary.update(unit_glossary)
        brand_context["glossary"] = existing_glossary

    # --- Step 4.5: Domain rules ---
    domain_rules = {}
    if domain_name:
        domain = await domain_svc.get_by_name(domain_name)
        if domain and domain.rules:
            domain_rules = domain.rules

    # --- Step 5: Complexity routing & translation ---
    complexity_score = calculate_complexity_score(text)

    try:
        translation_text = await translate(
            text, source_lang, target_lang, complexity_score, brand_context, domain_rules
        )
        is_successed = True
        notes = None
    except NotImplementedError as e:
        translation_time = time.time() - start_time
        await translation_svc.create(
            value=text,
            language=source_lang,
            translation=None,
            translation_language=target_lang,
            detected_input_lang=detected_input_lang,
            is_successed=False,
            notes=str(e),
            translation_time=translation_time,
            input_size=len(text),
            output_size=0,
            filename=filename,
            property=property_name,
        )
        return {"error": str(e), "complexity_score": complexity_score}
    except Exception as e:
        translation_text = None
        is_successed = False
        notes = str(e)

    translation_time_elapsed = time.time() - start_time

    # --- Step 6: Quality scoring ---
    comet_score = None
    if is_successed and translation_text:
        try:
            comet_score = score_translation(text, translation_text)
        except Exception as e:
            logger.warning("Quality scoring failed: %s", e)
            comet_score = None

    # --- Step 7: Persist with cache fields ---
    new_record = await translation_svc.save_with_cache_fields(
        value=text,
        language=source_lang,
        translation=translation_text,
        translation_language=target_lang,
        detected_input_lang=detected_input_lang,
        detected_output_lang=target_lang,
        is_successed=is_successed,
        score=comet_score,
        notes=notes,
        translation_time=translation_time_elapsed,
        input_size=len(text),
        output_size=len(translation_text) if translation_text else 0,
        size_difference=(
            (len(translation_text) - len(text)) / len(text) * 100
            if translation_text
            else None
        ),
        filename=filename,
        property=property_name,
    )

    return {
        "message": "Translation completed" if is_successed else f"Translation failed: {notes}",
        "translation": translation_text,
        "score": comet_score,
        "complexity_score": complexity_score,
        "detected_input_lang": detected_input_lang,
    }


async def detect_language_controller(payload: DetectionRequest) -> dict:
    """Detect the language of input text using langdetect."""
    compat = is_source_target_compatible(payload.text, "")
    return {"detected_language": compat["detected_lang"]}


async def translate_document_controller(
    payload: DocumentTranslationRequest,
    db: AsyncSession,
    brand_uuid: str | None = None,
    domain_name: str | None = None,
) -> dict:
    """
    Document translation: fetches document from URL, converts to AST,
    translates each segment, and reconstitutes the document.
    """
    source_lang = payload.source_lang
    target_lang = payload.target_lang
    document_url = payload.document_url

    # 1. Check supported languages
    if not is_in_supported_languages(source_lang, target_lang):
        return {"error": f"Language pair {source_lang}->{target_lang} is not supported"}

    # 2. Extract filename from URL
    try:
        parsed_url = urlparse(document_url)
        filename = os.path.basename(parsed_url.path) or "document.json"
    except Exception:
        filename = "document.json"

    # 3. Fetch file content
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(document_url)
            response.raise_for_status()
            doc_data = response.json()
        except httpx.HTTPError as e:
            return {"error": f"Failed to fetch document: {str(e)}"}
        except ValueError as e:
            return {"error": f"Document is not valid JSON: {str(e)}"}

    # 4. Parse JSON to AST
    try:
        root_node = json_to_ast(doc_data)
        doc_node = DocumentNode(root_node, "json")
    except Exception as e:
        return {"error": f"Failed to parse document to AST: {str(e)}"}

    # 5. Collect and translate translatable segments
    translatable_nodes = collect_translatable_nodes(doc_node)
    
    for node in translatable_nodes:
        # Wrap each segment in a TranslationRequest
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
                domain_name=domain_name,
                filename=filename,
                property_name=node.path,
            )
            if "error" in res:
                logger.warning("Failed to translate segment '%s' in path %s: %s", node.value[:30], node.path, res["error"])
                node.translated_value = node.value
            else:
                node.translated_value = res.get("translation", node.value)
        except Exception as e:
            logger.error("Error translating segment '%s': %s", node.value[:30], e)
            node.translated_value = node.value

    # 6. Reconstitute the document from AST
    translated_document = doc_node.to_dict()

    return {
        "message": "Document translation completed successfully",
        "data": {
            "document_url": document_url,
            "source_lang": source_lang,
            "target_lang": target_lang,
        },
        "translated_document": translated_document,
    }
