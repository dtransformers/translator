import logging
from typing import List

logger = logging.getLogger(__name__)

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Model loaded successfully.")
        except ImportError:
            logger.error("sentence-transformers is not installed.")
            raise
    return _embedding_model

def get_embedding(text: str) -> List[float]:
    """
    Generates a dense vector embedding for the given text.
    """
    if not text.strip():
        return [0.0] * 384
        
    model = get_embedding_model()
    embedding = model.encode(text)
    return embedding.tolist()
