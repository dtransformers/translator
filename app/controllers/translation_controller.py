# Controller module setup to handle the business logic
import time
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.translations.repository import TranslationRepository
from app.pipeline.verification import (
    is_translatable,
    is_source_target_compatible,
    is_in_supported_languages,
)
from app.pipeline.cache import get_translation_cache
from app.pipeline.complexity import calculate_complexity_score
from app.pipeline.translation import translate
from app.pipeline.quality import score_translation

logger = logging.getLogger(__name__)


async def translate_text_controller(payload: dict, db: AsyncSession) -> dict:
    source_lang = payload.get("source_lang")
    target_lang = payload.get("target_lang")
    text = payload.get("text")

    if not source_lang or not target_lang or not text:
        return {"error": "Missing source_lang, target_lang, or text in payload"}

    start_time = time.time()
    repo = TranslationRepository(db)

    # ── Step 1: IsTheInputTranslizable ──
    if not is_translatable(text):
        translation_time = time.time() - start_time
        await repo.create_translation(
            value=text, language=source_lang,
            translation=text, translation_language=target_lang,
            is_successed=True,
            notes="Skipped: Input is not translatable (emoji/link/number/HTML)",
            translation_time=translation_time,
            input_size=len(text), output_size=len(text),
        )
        return {"translation": text, "skipped": True, "reason": "not_translatable"}

    # ── Step 2: IsTheInputSourceTargetCompatible ──
    compat = is_source_target_compatible(text, source_lang)
    detected_input_lang = compat["detected_lang"]

    # ── Step 3: IsTheInputInSupportedLanguages ──
    if not is_in_supported_languages(source_lang, target_lang):
        return {"error": f"Language pair {source_lang}->{target_lang} is not supported"}

    # ── Step 4: IsTheInputHasTranslationCache ──
    cached = await get_translation_cache(text, source_lang, target_lang, db)
    if cached:
        return {
            "translation": cached.translation,
            "cached": True,
            "score": cached.score,
            "db_id": cached.id,
        }

    # ── Step 5: IsTheInputTransibleUsingMT (complexity) ──
    complexity_score = calculate_complexity_score(text)

    # ── Translation Step ──
    try:
        translation_text = translate(text, source_lang, target_lang, complexity_score)
        is_successed = True
        notes = None
    except NotImplementedError as e:
        # Complex text — not ready yet
        translation_time = time.time() - start_time
        await repo.create_translation(
            value=text, language=source_lang,
            translation=None, translation_language=target_lang,
            detected_input_lang=detected_input_lang,
            is_successed=False, notes=str(e),
            translation_time=translation_time,
            input_size=len(text), output_size=0,
        )
        return {"error": str(e), "complexity_score": complexity_score}
    except Exception as e:
        translation_text = None
        is_successed = False
        notes = str(e)

    translation_time_elapsed = time.time() - start_time

    # ── Return Step: COMETKiwi quality scoring ──
    comet_score = None
    if is_successed and translation_text:
        try:
            comet_score = score_translation(text, translation_text)
        except Exception as e:
            logger.warning(f"COMETKiwi scoring failed: {e}")
            comet_score = None

    # ── Save to database ──
    new_record = await repo.create_translation(
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
        size_difference=(len(translation_text) - len(text)) / len(text) * 100
        if translation_text else None,
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


async def detect_language_controller(payload: dict) -> dict:
    """Detect the language of input text using langdetect."""
    text = payload.get("text")
    if not text:
        return {"error": "Missing text in payload"}

    compat = is_source_target_compatible(text, "")
    return {"detected_language": compat["detected_lang"]}


async def translate_document_controller(payload: dict) -> dict:
    # TODO: Implement document translation logic here
    return {"message": "translate document controller executed", "data": payload}
