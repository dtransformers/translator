"""
Translation controller — thin orchestrator that delegates to entity services.

No direct repository access. All DB operations go through:
    - TranslationService (translations entity)
    - BrandService (brands entity)
"""

import time
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.translations.service import TranslationService
from app.brands.service import BrandService
from app.pipeline.verification import (
    is_translatable,
    is_source_target_compatible,
    is_in_supported_languages,
)
from app.pipeline.complexity import calculate_complexity_score
from app.pipeline.translation import translate
from app.pipeline.quality import score_translation
from app.schemas.translation import (
    TranslationRequest,
    DetectionRequest,
    DocumentTranslationRequest,
)

logger = logging.getLogger(__name__)


async def translate_text_controller(payload: TranslationRequest, db: AsyncSession) -> dict:
    """
    Orchestrate the full translation pipeline:
    verify → cache check → complexity → translate → quality score → persist.
    """
    source_lang = payload.source_lang
    target_lang = payload.target_lang
    text = payload.text
    brand_uuid = payload.brand_uuid

    translation_svc = TranslationService(db)
    brand_svc = BrandService(db)

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
        )
        return {"translation": text, "skipped": True, "reason": "not_translatable"}

    # --- Step 2: Language compatibility ---
    compat = is_source_target_compatible(text, source_lang)
    detected_input_lang = compat["detected_lang"]

    if not is_in_supported_languages(source_lang, target_lang):
        return {"error": f"Language pair {source_lang}->{target_lang} is not supported"}

    # --- Step 3: Cache lookup ---
    cached = await translation_svc.find_cached(text, source_lang, target_lang)
    if cached:
        return {
            "translation": cached.translation,
            "cached": True,
            "score": cached.score,
            "db_id": cached.id,
        }

    # --- Step 4: Brand context ---
    brand_context = await brand_svc.get_brand_context(brand_uuid)

    # Merge reusable units into the brand glossary
    unit_glossary = await translation_svc.build_glossary_from_units(text, target_lang)
    if unit_glossary:
        existing_glossary = brand_context.get("glossary", {})
        existing_glossary.update(unit_glossary)
        brand_context["glossary"] = existing_glossary

    # --- Step 5: Complexity routing & translation ---
    complexity_score = calculate_complexity_score(text)

    try:
        translation_text = translate(
            text, source_lang, target_lang, complexity_score, brand_context
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
    )

    return {
        "message": "Translation completed",
        "translation": translation_text,
        "db_id": new_record.id,
        "is_successed": is_successed,
        "score": comet_score,
        "complexity_score": complexity_score,
        "detected_input_lang": detected_input_lang,
    }


async def detect_language_controller(payload: DetectionRequest) -> dict:
    """Detect the language of input text using langdetect."""
    compat = is_source_target_compatible(payload.text, "")
    return {"detected_language": compat["detected_lang"]}


async def translate_document_controller(payload: DocumentTranslationRequest) -> dict:
    """Document translation (stub — to be implemented)."""
    return {
        "message": "translate document controller executed",
        "data": payload.model_dump(),
    }
