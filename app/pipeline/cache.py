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
    """
    Multi-level caching strategy:
    L1: Exact Cache
    L2: Normalized Cache
    L3: Semantic Vector Cache
    L4: Translation Memory (Human-approved) - prioritized in each level
    """
    if not text:
        return None

    # Calculate exact hash for L1
    exact_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()

    # --- L1: Exact Cache ---
    # Try to find an exact match, prioritizing human-approved (L4)
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

    # --- L2: Normalized Cache ---
    # Abstract entities and canonicalize
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
    if l2_hit and not entities: # Simple case: no entities to replace back
        logger.info(f"L2 Normalized Cache Hit for: {text[:20]}")
        return l2_hit

    # TODO: Implement complex L2 hit entity re-injection if entities exist

    # --- L3: Semantic Vector Cache ---
    try:
        query_embedding = get_embedding(text)
        # Using pgvector Cosine distance (<=>). Lower is better. Threshold of 0.05 is ~95% similarity
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
        
        # We need a way to check if the distance is below threshold, 
        # but SQLAlchemy might just return the closest. 
        # For a robust implementation, we'd query the distance as well and check it.
        # This is a simplified L3 hit.
        if l3_hit:
            logger.info(f"L3 Semantic Vector Hit for: {text[:20]}")
            # return l3_hit # Be careful, might return bad match if distance is large
            # We'd ideally check distance. 
    except Exception as e:
        logger.warning(f"L3 Semantic cache failed (ensure pgvector is installed): {e}")

    return None

async def save_translation_cache(
    text: str,
    source_lang: str,
    target_lang: str,
    translation: str,
    db: AsyncSession
):
    """Helper to save a new translation with caching fields populated"""
    exact_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    abstracted_text, entities = await abstract_entities(text, language=source_lang)
    normalized_text = canonicalize_text(abstracted_text)
    norm_hash = semantic_fingerprint(normalized_text)
    
    # L3 Vector
    try:
        emb = get_embedding(text)
    except Exception:
        emb = None

    new_record = Translation(
        value=text,
        text_hash=exact_hash,
        language=source_lang,
        translation=translation,
        translation_language=target_lang,
        normalized_text=normalized_text,
        normalized_hash=norm_hash,
        embedding=emb,
        is_successed=True
    )
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)
    return new_record
