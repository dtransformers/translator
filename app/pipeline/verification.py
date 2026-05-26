import re
import emoji
from langdetect import detect, LangDetectException

# Supported language codes
SUPPORTED_LANGUAGES = {"en", "fr", "es", "ar", "zh"}

# Supported directional pairs (source, target)
SUPPORTED_PAIRS = {
    ("en", "fr"), ("fr", "en"),
    ("en", "es"), ("es", "en"),
    ("en", "ar"), ("ar", "en"),
    ("en", "zh"), ("zh", "en"),
}

# Regex patterns for untranslatable content
URL_PATTERN = re.compile(
    r'^(https?://|www\.)\S+$', re.IGNORECASE
)
HTML_TAG_PATTERN = re.compile(
    r'^(\s*<[^>]+>\s*)+$', re.DOTALL
)
NUMBER_CURRENCY_PATTERN = re.compile(
    r'^[\d\s\.\,\$\€\£\¥\₹\%\+\-\*/=]+$'
)


def is_translatable(text: str) -> bool:
    """
    Step 1: IsTheInputTranslizable
    Returns False if the text consists entirely of untranslatable content
    (links, emojis, numbers, currency symbols, HTML tags, etc.)
    """
    stripped = text.strip()
    if not stripped:
        return False

    # Check if entirely URLs
    if URL_PATTERN.match(stripped):
        return False

    # Check if entirely HTML tags
    if HTML_TAG_PATTERN.match(stripped):
        return False

    # Check if entirely numbers / currency symbols
    if NUMBER_CURRENCY_PATTERN.match(stripped):
        return False

    # Check if entirely emojis (and whitespace)
    non_space = stripped.replace(" ", "")
    if non_space and all(emoji.is_emoji(ch) for ch in non_space):
        return False

    return True


def is_source_target_compatible(text: str, source_lang: str) -> dict:
    """
    Step 2: IsTheInputSourceTargetCompatible
    Detects the actual language of the text and checks if it matches
    the declared source language.
    Returns a dict with 'compatible' (bool) and 'detected_lang' (str or None).
    """
    try:
        detected = detect(text)
    except LangDetectException:
        return {"compatible": False, "detected_lang": None}

    # langdetect returns 'zh-cn', 'zh-tw' for Chinese — normalise to 'zh'
    if detected.startswith("zh"):
        detected = "zh"

    return {
        "compatible": detected == source_lang,
        "detected_lang": detected
    }


def is_in_supported_languages(source_lang: str, target_lang: str) -> bool:
    """
    Step 3: IsTheInputInSupportedLanguages
    Validates the requested source and target are in our supported set and
    that the directional pair exists.
    """
    if source_lang not in SUPPORTED_LANGUAGES:
        return False
    if target_lang not in SUPPORTED_LANGUAGES:
        return False
    if (source_lang, target_lang) not in SUPPORTED_PAIRS:
        return False
    return True



