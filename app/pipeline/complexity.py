import re
import logging
import textstat
import asyncio
from typing import Optional, Dict
from wordfreq import zipf_frequency
from transformers import pipeline


logger = logging.getLogger(__name__)

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
VAR_PATTERN = re.compile(r"\{\{[^}]*\}\}|\{[^}]*\}|%s|%d")
MARKDOWN_PATTERN = re.compile(r"\[[^\]]*\]\([^)]*\)")

# Point budget per signal; plain text alone can reach 70, so routing does not depend on markup
READABILITY_MAX_POINTS = 40
SENTENCE_LENGTH_MAX_POINTS = 15
VOCABULARY_MAX_POINTS = 15

# v-urushkin/xlm-roberta-base-readability is a single-output regression model where higher
# means easier; measured outputs run from about +0.7 (children's text) to -2.7 (dense jargon)
READABILITY_EASY = 1.0
READABILITY_HARD = -3.0

_readability_pipe = None
_models_loaded = False
_cache = {}

def _load_models():
    global _readability_pipe, _models_loaded
    if _models_loaded or not pipeline:
        return
    try:
        logger.info("Loading readability model (v-urushkin/xlm-roberta-base-readability)...")
        _readability_pipe = pipeline("text-classification", model="v-urushkin/xlm-roberta-base-readability")
    except Exception as e:
        logger.exception(f"Failed to load readability model: {e}")
        
    _models_loaded = True

def _get_wordfreq_score(text: str) -> float:
    if not zipf_frequency:
        return 0
    words = [w for w in re.findall(r'\b\w+\b', text.lower()) if not w.isnumeric()]
    if not words:
        return 0
    freqs = [zipf_frequency(w, 'en') for w in words]
    valid_freqs = [f for f in freqs if f > 0]
    if not valid_freqs:
        return VOCABULARY_MAX_POINTS
    avg_freq = sum(valid_freqs) / len(valid_freqs)
    complexity = max(0, (6.0 - avg_freq) * 5)
    return min(VOCABULARY_MAX_POINTS, complexity)

def _get_jargon_score(text: str, brand_context: Optional[Dict], domain_rules: Optional[Dict]) -> int:
    score = 0
    text_lower = text.lower()
    
    if brand_context and "glossary" in brand_context:
        for term in brand_context["glossary"].keys():
            if term.lower() in text_lower:
                score += 5
                
    if domain_rules and "jargon" in domain_rules:
        for term in domain_rules["jargon"]:
            if term.lower() in text_lower:
                score += 5
                
    return min(15, score)

def _get_sentence_length_score(text: str) -> float:
    try:
        sentences = max(1, textstat.sentence_count(text))
        words = textstat.lexicon_count(text)
        avg_words = words / sentences
        if avg_words > 12:
            return min(SENTENCE_LENGTH_MAX_POINTS, avg_words - 12)
    except Exception:
        pass
    return 0.0

def _readability_raw(text: str) -> Optional[float]:
    if not _readability_pipe:
        return None
    try:
        return float(_readability_pipe(text[:512], truncation=True, function_to_apply="none")[0]["score"])
    except Exception:
        return None

def _readability_points(raw: Optional[float]) -> float:
    if raw is None:
        return 0.0
    hardness = (READABILITY_EASY - raw) / (READABILITY_EASY - READABILITY_HARD)
    return max(0.0, min(1.0, hardness)) * READABILITY_MAX_POINTS

def _get_model_score(text: str) -> float:
    return _readability_points(_readability_raw(text))

async def _get_llm_fallback_score(text: str, current_score: int) -> int:
    try:
        from app.core.config import settings
        from app.llms.model import get_llm
        from app.llms.prompts import get_complexity_rating_prompt
        from app.llms.schemas import ComplexityRating
        threshold = settings.COMPLEXITY_THRESHOLD
        if threshold - settings.COMPLEXITY_LLM_WINDOW <= current_score <= threshold + settings.COMPLEXITY_LLM_WINDOW:
            chain = get_complexity_rating_prompt() | get_llm().with_structured_output(
                ComplexityRating, method="json_schema"
            )
            rating = await chain.ainvoke({"text": text})
            return int((current_score + rating.score) / 2)
    except Exception as e:
        logger.debug(f"LLM fallback failed: {e}")
    return current_score

async def calculate_complexity_score(text: str, brand_context: Optional[Dict] = None, domain_rules: Optional[Dict] = None) -> int:
    if not text:
        return 0

    cache_key = (text, str(brand_context), str(domain_rules))
    if cache_key in _cache:
        return _cache[cache_key]

    _load_models()
    score = 0
    text_length = len(text)
    
    # 1. Structural Complexity
    if HTML_TAG_PATTERN.search(text): score += 15
    if VAR_PATTERN.search(text): score += 15
    if MARKDOWN_PATTERN.search(text): score += 5
        
    if text_length < 15 and score == 0:
        return 0

    # 2. Sentence Length
    score += _get_sentence_length_score(text)

    # 3. Vocabulary Complexity
    score += _get_wordfreq_score(text)

    # 4. Technical Jargon Density
    score += _get_jargon_score(text, brand_context, domain_rules)

    # 5. Readability Model
    score += _get_model_score(text)

    final_score = int(max(0, min(100, score)))

    # 6. LLM Fallback
    final_score = await _get_llm_fallback_score(text, final_score)

    _cache[cache_key] = final_score
    if len(_cache) > 10000:
        _cache.pop(next(iter(_cache)))

    return final_score
