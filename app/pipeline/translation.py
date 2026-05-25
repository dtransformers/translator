import logging
from app.machine_translation import marian_mt_service

logger = logging.getLogger(__name__)

# Complexity threshold: scores at or above this are considered "complex"
COMPLEXITY_THRESHOLD = 50


def translate(text: str, source_lang: str, target_lang: str, complexity_score: int) -> str:

    if complexity_score >= COMPLEXITY_THRESHOLD:
        raise NotImplementedError(
            f"Input complexity score is {complexity_score}/{COMPLEXITY_THRESHOLD}. "
            f"Complex translation is not ready yet for translation."
        )

    logger.info(
        f"Translating with MarianMT (complexity={complexity_score}): "
        f"{source_lang} -> {target_lang}"
    )
    return marian_mt_service.translate_text(text, source_lang, target_lang)
