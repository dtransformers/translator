import logging
import torch
from transformers import AutoTokenizer, AutoModel

logger = logging.getLogger(__name__)

_tokenizer = None
_model = None

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def _get_model():
    global _tokenizer, _model
    if _model is None:
        logger.info(f"Loading quality estimation model: {MODEL_NAME}...")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModel.from_pretrained(MODEL_NAME)
        _model.eval()
        logger.info("Quality estimation model loaded.")
    return _tokenizer, _model


def _mean_pooling(model_output, attention_mask):
    token_embeddings = model_output.last_hidden_state
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
        input_mask_expanded.sum(1), min=1e-9
    )


def score_translation(source: str, translation: str) -> float:
    tokenizer, model = _get_model()
    encoded = tokenizer(
        [source, translation],
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    )
    with torch.no_grad():
        output = model(**encoded)

    embeddings = _mean_pooling(output, encoded["attention_mask"])
    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

    cosine_sim = torch.nn.functional.cosine_similarity(
        embeddings[0].unsqueeze(0), embeddings[1].unsqueeze(0)
    )

    score = round(cosine_sim.item(), 4)
    logger.info(f"Quality score (cosine similarity): {score}")
    return score
