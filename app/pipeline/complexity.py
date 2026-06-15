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

_readability_pipe = None
_lcp_pipe = None
_models_loaded = False
_cache = {}

def _load_models():
    global _readability_pipe, _lcp_pipe, _models_loaded
    if _models_loaded or not pipeline:
        return
    try:
        logger.info("Loading readability model (v-urushkin/xlm-roberta-base-readability)...")
        _readability_pipe = pipeline("text-classification", model="v-urushkin/xlm-roberta-base-readability")
    except Exception as e:
        logger.exception(f"Failed to load readability model: {e}")
        
    try:
        logger.info("Loading LCP model (roberta-base-complex-word-identification)...")
        _lcp_pipe = pipeline("text-classification", model="bhavsarpratik/roberta-base-complex-word-identification")
    except Exception as e:
        logger.exception(f"Failed to load LCP model: {e}")
        
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
        return 10 
    avg_freq = sum(valid_freqs) / len(valid_freqs)
    complexity = max(0, (6.0 - avg_freq) * 3) 
    return min(10, complexity)

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
        if avg_words > 20:
            return min(10, (avg_words - 20) * 0.5)
    except Exception:
        pass
    return 0.0

def _get_model_score(text: str) -> float:
    model_score = 0.0
    try:
        if _readability_pipe:
            res = _readability_pipe(text[:512], truncation=True)[0]
            if "complex" in str(res['label']).lower() or "hard" in str(res['label']).lower():
                model_score += 15 * res['score']
            else:
                model_score += 5
    except Exception:
        pass

    try:
        if _lcp_pipe:
            res = _lcp_pipe(text[:512], truncation=True)[0]
            if "complex" in str(res['label']).lower():
                model_score += 15 * res['score']
    except Exception:
        pass
    return min(30, model_score)

async def _get_llm_fallback_score(text: str, current_score: int) -> int:
    try:
        from app.core.config import settings
        from app.llms.model import get_llm
        threshold = settings.COMPLEXITY_THRESHOLD
        if threshold - 5 <= current_score <= threshold + 5:
            llm = get_llm()
            prompt = f"Rate the translation complexity of the following text from 0 to 100, where 100 is highly complex. Output ONLY the integer.\n\nText: {text}"
            response = await llm.ainvoke(prompt)
            llm_score = int(re.search(r'\d+', response.content).group())
            return int((current_score + llm_score) / 2)
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

    # 5. Readability & LCP Models
    score += _get_model_score(text)

    final_score = int(max(0, min(100, score)))

    # 6. LLM Fallback
    final_score = await _get_llm_fallback_score(text, final_score)

    _cache[cache_key] = final_score
    if len(_cache) > 10000:
        _cache.pop(next(iter(_cache)))

    return final_score
