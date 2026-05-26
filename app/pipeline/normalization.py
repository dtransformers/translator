import re
import unicodedata
import hashlib
import httpx
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

from app.core.config import settings

DUCKLING_URL = settings.DUCKLING_URL
def canonicalize_text(text: str) -> str:
    """
    Trims, lowercases, unicode normalizes, collapses spaces, and removes punctuation noise.
    """
    if not text:
        return ""
    
    # Unicode normalize
    text = unicodedata.normalize("NFKC", text)
    # Lowercase
    text = text.lower()
    # Remove punctuation noise (keeping basic sentence structure punctuation if needed, 
    # but for cache hashing we might want to strip most non-alphanumeric depending on strictness)
    # Here we keep alphanumeric and basic spaces.
    text = re.sub(r'[^\w\s]', '', text)
    # Collapse spaces
    text = re.sub(r'\s+', ' ', text)
    # Trim
    return text.strip()

async def extract_entities_duckling(text: str, language: str = "en_XX") -> List[Dict[str, Any]]:
    """
    Calls Duckling server to extract entities (dates, numbers, etc).
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DUCKLING_URL,
                data={"text": text, "locale": language}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.warning(f"Duckling extraction failed: {e}")
        return []

async def abstract_entities(text: str, language: str = "en_XX") -> tuple[str, List[Dict[str, Any]]]:
    """
    Abstracts entities from text using Duckling.
    Returns the abstracted text and the list of extracted entities.
    """
    entities = await extract_entities_duckling(text, language)
    
    if not entities:
        return text, []

    # Sort entities by start index descending to avoid offset issues when replacing
    entities.sort(key=lambda x: x['start'], reverse=True)
    
    abstracted_text = text
    for i, entity in enumerate(entities):
        start = entity['start']
        end = entity['end']
        dim = entity['dim'].upper()
        placeholder = f"{{{{{dim}_{i}}}}}"
        abstracted_text = abstracted_text[:start] + placeholder + abstracted_text[end:]
        
        # Add placeholder to entity info for reconstruction later
        entity['placeholder'] = placeholder

    return abstracted_text, entities

def semantic_fingerprint(text: str) -> str:
    """
    Generates a SHA256 hash of the normalized text.
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def segment_text(text: str) -> List[str]:
    """
    Basic hierarchical segmentation.
    Splits text into sentences.
    """
    import nltk
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
        
    sentences = nltk.tokenize.sent_tokenize(text)
    return sentences
