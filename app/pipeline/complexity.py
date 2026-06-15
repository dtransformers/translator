import logging
import textstat

logger = logging.getLogger(__name__)

def calculate_complexity_score(text: str) -> int:
    try:
        flesch = textstat.flesch_reading_ease(text)
        return int(100 - max(0.0, min(100.0, flesch)))
    except Exception:
        return 50

