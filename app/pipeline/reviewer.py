"""
Batch translation reviewer module.
Scans the database for translations that have low trust score and high complexity,
and corrects them using the LLM.
"""

import asyncio
import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.translations.models import Translation
from app.pipeline.complexity import calculate_complexity_score
from app.pipeline.quality import score_translation
from app.llms.model import get_llm
from app.llms.prompts import get_fix_translation_prompt

logger = logging.getLogger(__name__)

async def fix_translation_with_llm(source_text: str, bad_translation: str, target_lang: str) -> str:
    """Uses the LLM to fix a poorly translated text."""
    try:
        llm = get_llm()
        prompt = get_fix_translation_prompt()
        chain = prompt | llm
        
        response = await chain.ainvoke({
            "target_language": target_lang,
            "source_text": source_text,
            "bad_translation": bad_translation
        })
        
        # Clean up possible markdown wrappers
        content = response.content.strip()
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
            
        return content
    except Exception as e:
        logger.error(f"Failed to fix translation with LLM: {e}")
        return bad_translation

async def review_translations_batch(db: AsyncSession) -> dict:
    """
    Scans the translations table for items needing review:
    Condition: trust_score < 0.8 AND complexity_score > 35
    """
    logger.info("Starting batch translation review...")
    
    # 1. Fetch translations that might need review
    # We fetch those where trust_score is NULL or < 0.8.
    stmt = select(Translation).where(
        Translation.is_successed == True,
    )
    
    result = await db.execute(stmt)
    translations = result.scalars().all()
    
    reviewed_count = 0
    fixed_count = 0
    
    for t in translations:
        needs_update = False
        
        if t.complexity_score is None:
            t.complexity_score = calculate_complexity_score(t.value)
            needs_update = True
            
        if t.trust_score is None:
            if t.score is not None:
                t.trust_score = t.score
            else:
                if t.translation:
                    t.trust_score = await asyncio.to_thread(score_translation, t.value, t.translation)
            needs_update = True
            
        # Review condition: trust_score <= 0.85 and complexity >= 35
        if t.trust_score is not None and t.trust_score <= 0.85 and t.complexity_score >= 35:
            logger.info(f"Reviewing translation ID {t.id} (Trust: {t.trust_score}, Complexity: {t.complexity_score})")
            reviewed_count += 1
            
            fixed_translation = await fix_translation_with_llm(
                source_text=t.value,
                bad_translation=t.translation,
                target_lang=t.translation_language
            )
            
            if fixed_translation and fixed_translation != t.translation:
                t.translation = fixed_translation
                # Rescore the fixed translation
                new_trust_score = await asyncio.to_thread(score_translation, t.value, t.translation)
                t.trust_score = new_trust_score
                # Also update legacy score
                t.score = new_trust_score
                t.is_verified = True  # Mark as verified by LLM
                needs_update = True
                fixed_count += 1
                
        if needs_update:
            db.add(t)
            await db.commit()
            
    logger.info(f"Batch review complete. Reviewed: {reviewed_count}, Fixed: {fixed_count}")
    return {"reviewed": reviewed_count, "fixed": fixed_count}
