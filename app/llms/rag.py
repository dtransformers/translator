import logging
from typing import List, Dict, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.translations.service import TranslationService

logger = logging.getLogger(__name__)

async def retrieve_rag_examples(
    translation_svc: "TranslationService",
    text: str,
    source_lang: str,
    target_lang: str,
    limit: int = 3,
) -> List[Dict[str, str]]:
    """
    Retrieve semantically similar approved translations from the database using pgvector
    and format them for LLM few-shot context.
    """
    try:
        similar_records = await translation_svc.retrieve_similar_translations(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            limit=limit,
        )
        return [
            {"source": r.value, "translation": r.translation}
            for r in similar_records
            if r.translation
        ]
    except Exception as e:
        logger.warning("Failed to retrieve RAG examples: %s", e)
        return []
