import logging
from app.machine_translation import marian_mt_service

logger = logging.getLogger(__name__)

COMPLEXITY_THRESHOLD = 50


import json
from app.llms.model import get_llm
from app.llms.prompts import get_translation_draft_prompt

def translate_with_llm(text: str, source_lang: str, target_lang: str) -> str:
    logger.info(f"Using LLM for translation from {source_lang} to {target_lang}")
    llm = get_llm()
    prompt = get_translation_draft_prompt()
    chain = prompt | llm
    
    response = chain.invoke({
        "source_language": source_lang,
        "target_language": target_lang,
        "industry": "General",
        "summary": "General text",
        "glossary": "{}",
        "texts": json.dumps([text])
    })
    
    try:
        content = response.content.replace("```json", "").replace("```", "").strip()
        translated_list = json.loads(content)
        if isinstance(translated_list, list) and len(translated_list) > 0:
            return translated_list[0]
        return response.content
    except Exception as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return response.content


def translate(text: str, source_lang: str, target_lang: str, complexity_score: int) -> str:

    if complexity_score >= COMPLEXITY_THRESHOLD:
        logger.info(
            f"Input complexity score is {complexity_score}/{COMPLEXITY_THRESHOLD}. "
            f"Falling back to LLM translation."
        )
        return translate_with_llm(text, source_lang, target_lang)

    logger.info(
        f"Translating with MarianMT (complexity={complexity_score}): "
        f"{source_lang} -> {target_lang}"
    )
    return marian_mt_service.translate_text(text, source_lang, target_lang)
