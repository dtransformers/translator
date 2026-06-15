
import json
import logging
from typing import Any

import asyncio
from app.machine_translation import nllb_service
from app.llms.model import get_llm
from app.llms.prompts import get_translation_draft_prompt
from app.core.config import settings

logger = logging.getLogger(__name__)


async def translate_with_llm(
    text: str,
    source_lang: str,
    target_lang: str,
    brand_context: dict[str, Any] | None = None,
    domain_rules: dict[str, Any] | None = None,
    similar_examples: list[dict] | None = None,
) -> str:
    logger.info("Using LLM for translation from %s to %s", source_lang, target_lang)

    ctx = brand_context or {}
    llm = get_llm()
    prompt = get_translation_draft_prompt()
    chain = prompt | llm

    if similar_examples:
        rag_str = "\n".join(
            f"- Source: \"{item['source']}\"\n  Translation: \"{item['translation']}\""
            for item in similar_examples
        )
    else:
        rag_str = "None"

    response = await chain.ainvoke({
        "source_language": source_lang,
        "target_language": target_lang,
        "industry": ctx.get("industry", "General"),
        "summary": ctx.get("summary", "General text"),
        "glossary": json.dumps(ctx.get("glossary", {})),
        "domain_rules": json.dumps(domain_rules or {}),
        "rag_examples": rag_str,
        "texts": json.dumps([text]),
    })

    raw_content = response.content
    content = str(raw_content) if not isinstance(raw_content, list) else " ".join(map(str, raw_content))

    try:
        content_clean = content.replace("```json", "").replace("```", "").strip()
        translated_list = json.loads(content_clean)
        if isinstance(translated_list, list) and len(translated_list) > 0:
            return str(translated_list[0])
        return content
    except Exception as e:
        logger.exception("Failed to parse LLM response: %s", e)
        return content


async def translate(
    text: str,
    source_lang: str,
    target_lang: str,
    complexity_score: int,
    brand_context: dict[str, Any] | None = None,
    domain_rules: dict[str, Any] | None = None,
    similar_examples: list[dict] | None = None,
) -> str:
    """
    Route translation to NLLB-200 (simple texts) or LLM (complex texts).

    Args:
        text: Source text to translate.
        source_lang: Source language code.
        target_lang: Target language code.
        complexity_score: Computed complexity (0-100). >= threshold → LLM.
        brand_context: Optional brand context dict for LLM prompt enrichment.
        domain_rules: Optional domain rules.
        similar_examples: Optional similar examples for RAG.
    """
  
    
    requires_llm = False
    text_lower = text.lower()
    
    if brand_context:
        glossary = brand_context.get("glossary", {})
        if any(term.lower() in text_lower for term in glossary.keys()):
            requires_llm = True
            
        keywords = brand_context.get("keywords", [])
        if any(kw.lower() in text_lower for kw in keywords):
            requires_llm = True

    if not requires_llm and complexity_score >= settings.COMPLEXITY_THRESHOLD:
        requires_llm = True

    if requires_llm:
        logger.info(
            "Routing to LLM (complexity=%d/%d, brand_context_match=%s).",
            complexity_score,
            settings.COMPLEXITY_THRESHOLD,
            requires_llm and complexity_score < settings.COMPLEXITY_THRESHOLD
        )
        return await translate_with_llm(
            text, source_lang, target_lang, brand_context, domain_rules, similar_examples
        )

    logger.info(
        "Translating with NLLB-200 (complexity=%d): %s -> %s",
        complexity_score,
        source_lang,
        target_lang,
    )
    return await asyncio.to_thread(nllb_service.translate_text, text, source_lang, target_lang)


async def translate_json_with_llm(
    pruned_json: dict[str, str],
    source_lang: str,
    target_lang: str,
    brand_context: dict[str, Any] | None = None,
    domain_rules: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Translates a dictionary of flattened/pruned json nodes returning a dict with identical keys."""
    if not pruned_json:
        return {}

    ctx = brand_context or {}
    llm = get_llm()
    prompt = get_translation_draft_prompt()
    chain = prompt | llm

    # Dump the pruned json into the prompt
    response = await chain.ainvoke({
        "source_language": source_lang,
        "target_language": target_lang,
        "industry": ctx.get("industry", "General"),
        "summary": ctx.get("summary", "Translate this JSON object values. Return ONLY valid JSON with identical keys."),
        "glossary": json.dumps(ctx.get("glossary", {})),
        "domain_rules": json.dumps(domain_rules or {}),
        "rag_examples": "None",
        "texts": json.dumps(pruned_json, ensure_ascii=False),
    })

    raw_content = response.content
    content = str(raw_content) if not isinstance(raw_content, list) else " ".join(map(str, raw_content))
    
    # Strip markdown codeblocks
    content_clean = content.replace("```json", "").replace("```", "").strip()
    try:
        translated_dict = json.loads(content_clean)
        return translated_dict
    except json.JSONDecodeError:
        logger.exception("Failed to parse LLM JSON batch response.")
        return {}
