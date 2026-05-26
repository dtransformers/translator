import logging
import textstat
import nltk
from nltk.tokenize import word_tokenize

import os
import shutil
import zipfile

logger = logging.getLogger(__name__)

# Ensure nltk punkt tokenizer data is available
def _ensure_nltk_data():
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab", quiet=True)
    except zipfile.BadZipFile:
        logger.warning("Corrupt NLTK data found. Removing and re-downloading...")
        nltk_data_dir = os.path.expanduser("~/nltk_data/tokenizers")
        if os.path.exists(nltk_data_dir):
            shutil.rmtree(nltk_data_dir, ignore_errors=True)
        nltk.download("punkt_tab", quiet=True)

_ensure_nltk_data()



def calculate_complexity_score(text: str) -> int:
    char_count = len(text)
    if char_count < 50:
        length_score = 5
    elif char_count < 200:
        length_score = 10
    elif char_count < 500:
        length_score = 15
    elif char_count < 1000:
        length_score = 20
    else:
        length_score = 25

    try:
        tokens = word_tokenize(text)
    except Exception:
        tokens = text.split()

    total_words = len(tokens) if tokens else 1
    unique_words = len(set(t.lower() for t in tokens))
    type_token_ratio = unique_words / total_words  # 0..1

    vocab_score = int(type_token_ratio * 25)

    avg_word_len = sum(len(t) for t in tokens) / total_words if tokens else 0
    if avg_word_len < 4:
        word_len_score = 5
    elif avg_word_len < 6:
        word_len_score = 10
    elif avg_word_len < 8:
        word_len_score = 15
    elif avg_word_len < 10:
        word_len_score = 20
    else:
        word_len_score = 25

    try:
        flesch = textstat.flesch_reading_ease(text)
    except Exception:
        flesch = 50.0

    flesch_clamped = max(0.0, min(100.0, flesch))
    readability_score = int((1 - flesch_clamped / 100) * 25)

    raw_score = length_score + vocab_score + word_len_score + readability_score
    final_score = max(1, min(100, raw_score))

    logger.info(
        f"Complexity breakdown: length={length_score}, vocab={vocab_score}, "
        f"word_len={word_len_score}, readability={readability_score} => {final_score}"
    )

    return final_score
