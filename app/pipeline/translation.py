"""
Translation pipeline — routing logic between MarianMT and LLM.
"""

import json
import logging
from typing import Any

from app.machine_translation import marian_mt_service
from app.llms.model import get_llm
from app.llms.prompts import get_translation_draft_prompt

logger = logging.getLogger(__name__)

COMPLEXITY_THRESHOLD = 50


async def translate_with_llm(
    text: str,
    source_lang: str,
    target_lang: str,
    brand_context: dict[str, Any] | None = None,
    domain_rules: dict[str, Any] | None = None,
) -> str:
    """Translate text using the configured LLM, enriched with brand context."""
    logger.info("Using LLM for translation from %s to %s", source_lang, target_lang)

    ctx = brand_context or {}
    llm = get_llm()
    prompt = get_translation_draft_prompt()
    chain = prompt | llm

    response = await chain.ainvoke({
        "source_language": source_lang,
        "target_language": target_lang,
        "industry": ctx.get("industry", "General"),
        "summary": ctx.get("summary", "General text"),
        "glossary": json.dumps(ctx.get("glossary", {})),
        "domain_rules": json.dumps(domain_rules or {}),
        "texts": json.dumps([text]),
    })

    try:
        content = response.content.replace("```json", "").replace("```", "").strip()
        translated_list = json.loads(content)
        if isinstance(translated_list, list) and len(translated_list) > 0:
            return translated_list[0]
        return response.content
    except Exception as e:
        logger.error("Failed to parse LLM response: %s", e)
        return response.content


async def translate(
    text: str,
    source_lang: str,
    target_lang: str,
    complexity_score: int,
    brand_context: dict[str, Any] | None = None,
    domain_rules: dict[str, Any] | None = None,
) -> str:
    """
    Route translation to MarianMT (simple texts) or LLM (complex texts).

    Args:
        text: Source text to translate.
        source_lang: Source language code.
        target_lang: Target language code.
        complexity_score: Computed complexity (0-100). >= threshold → LLM.
        brand_context: Optional brand context dict for LLM prompt enrichment.
    """
    import asyncio
    
    if complexity_score >= COMPLEXITY_THRESHOLD:
        logger.info(
            "Input complexity score is %d/%d. Falling back to LLM translation.",
            complexity_score,
            COMPLEXITY_THRESHOLD,
        )
        return await translate_with_llm(text, source_lang, target_lang, brand_context, domain_rules)

    logger.info(
        "Translating with MarianMT (complexity=%d): %s -> %s",
        complexity_score,
        source_lang,
        target_lang,
    )
    return await asyncio.to_thread(marian_mt_service.translate_text, text, source_lang, target_lang)
