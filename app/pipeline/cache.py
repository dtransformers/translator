from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from app.translations.models import Translation, ReusableUnit
from app.pipeline.normalization import canonicalize_text, abstract_entities, semantic_fingerprint
from app.pipeline.embeddings import get_embedding
import hashlib
import logging

logger = logging.getLogger(__name__)

async def get_translation_cache(
    text: str,
    source_lang: str,
    target_lang: str,
    db: AsyncSession
) -> Translation | None:

    if not text:
        return None

    exact_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()


    l1_query = select(Translation).where(
        or_(Translation.value == text, Translation.text_hash == exact_hash),
        Translation.language == source_lang,
        Translation.translation_language == target_lang,
        Translation.is_successed == True
    ).order_by(Translation.is_approved.desc())
    
    l1_result = await db.execute(l1_query)
    l1_hit = l1_result.scalars().first()
    if l1_hit:
        logger.info(f"L1 Cache Hit for: {text[:20]}")
        return l1_hit

    abstracted_text, entities = await abstract_entities(text, language=source_lang)
    normalized_text = canonicalize_text(abstracted_text)
    norm_hash = semantic_fingerprint(normalized_text)

    l2_query = select(Translation).where(
        Translation.normalized_hash == norm_hash,
        Translation.language == source_lang,
        Translation.translation_language == target_lang,
        Translation.is_successed == True
    ).order_by(Translation.is_approved.desc())

    l2_result = await db.execute(l2_query)
    l2_hit = l2_result.scalars().first()
    if l2_hit and not entities:
        logger.info(f"L2 Normalized Cache Hit for: {text[:20]}")
        return l2_hit

    try:
        import asyncio
        query_embedding = await asyncio.to_thread(get_embedding, normalized_text)
        l3_query = select(Translation).where(
            Translation.language == source_lang,
            Translation.translation_language == target_lang,
            Translation.is_successed == True,
            Translation.embedding != None
        ).order_by(
            Translation.embedding.cosine_distance(query_embedding)
        ).limit(1)

        l3_result = await db.execute(l3_query)
        l3_hit = l3_result.scalars().first()
        
        if l3_hit:
            logger.info(f"L3 Semantic Vector Hit for: {text[:20]}")
    except Exception as e:
        logger.warning(f"L3 Semantic cache failed (ensure pgvector is installed): {e}")

    return None

from app.translations.repository import TranslationRepository

async def save_translation_cache(
    repo: TranslationRepository,
    **kwargs
):
    """Helper to save a new translation with caching fields populated"""
    text = kwargs.get("value")
    source_lang = kwargs.get("language")
    
    if text and source_lang:
        exact_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        abstracted_text, entities = await abstract_entities(text, language=source_lang)
        normalized_text = canonicalize_text(abstracted_text)
        norm_hash = semantic_fingerprint(normalized_text)
        
        # L3 Vector
        try:
            import asyncio
            emb = await asyncio.to_thread(get_embedding, normalized_text)
        except Exception:
            emb = None

        kwargs["text_hash"] = exact_hash
        kwargs["normalized_text"] = normalized_text
        kwargs["normalized_hash"] = norm_hash
        kwargs["embedding"] = emb

    return await repo.create_translation(**kwargs)
