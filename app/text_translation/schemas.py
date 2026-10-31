from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal, Optional


class TranslationSource(str, Enum):
    LLM = "llm"
    MACHINE_TRANSLATION = "machine_translation"
    EXACT_CACHE = "exact_cache"
    NORMALIZED_CACHE = "normalized_cache"
    SEMANTIC_CACHE = "semantic_cache"

class TranslationRequest(BaseModel):
    text: str = Field(..., description="The text to translate", min_length=1)
    source_lang: str = Field(..., description="The source language code (e.g., 'en', 'fr')", min_length=2, max_length=10)
    target_lang: str = Field(..., description="The target language code (e.g., 'es', 'ar')", min_length=2, max_length=10)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "Hello world, this is a test translation request.",
                    "source_lang": "en",
                    "target_lang": "es"
                }
            ]
        }
    }

class TranslationData(BaseModel):
    message: str = Field(..., description="Status message explaining the result")
    translation: Optional[str] = Field(None, description="The translated text, or the original text if skipped")
    source: Optional[TranslationSource] = Field(
        None,
        description=(
            "Where the translation came from: `llm`, `machine_translation` (NLLB-200), "
            "`exact_cache`, `normalized_cache` or `semantic_cache`. Null when skipped"
        ),
    )
    score: Optional[float] = Field(
        None,
        ge=-1.0,
        le=1.0,
        description=(
            "Semantic similarity between source and translation (multilingual-e5 cosine similarity). "
            "Typically 0.7–1.0; a meaning-preservation signal, not a full quality metric like COMET"
        ),
    )
    complexity_score: Optional[int] = Field(
        None, ge=0, le=100, description="Complexity of the source text (0–100); scores at or above the threshold are routed to the LLM"
    )
    detected_input_lang: Optional[str] = Field(None, description="The detected source language code, or null if detection failed or was skipped")
    cached: bool = Field(False, description="True if the translation was served from cache")
    skipped: bool = Field(False, description="True if the translation was skipped")
    reason: Optional[Literal["not_translatable"]] = Field(None, description="Reason code if skipped")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Translation completed",
                    "translation": "Hola mundo, esta es una solicitud de traducción de prueba.",
                    "source": "machine_translation",
                    "score": 0.89,
                    "complexity_score": 12,
                    "detected_input_lang": "en",
                    "cached": False,
                    "skipped": False
                }
            ]
        }
    }

class DetectionRequest(BaseModel):
    text: str = Field(..., description="The text to analyze and detect language for", min_length=1)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "Bonjour tout le monde"
                }
            ]
        }
    }

class DetectionData(BaseModel):
    detected_language: str = Field(..., description="The detected language code (e.g., 'fr', 'en')")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detected_language": "fr"
                }
            ]
        }
    }
