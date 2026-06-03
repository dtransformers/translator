from pydantic import BaseModel, Field
from typing import Optional

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
    score: Optional[float] = Field(None, description="Quality estimation (COMET) score of the translation")
    complexity_score: Optional[float] = Field(None, description="The computed complexity score of the source text")
    detected_input_lang: Optional[str] = Field(None, description="The detected source language code")
    cached: Optional[bool] = Field(None, description="True if the translation was served from cache")
    skipped: Optional[bool] = Field(None, description="True if the translation was skipped")
    reason: Optional[str] = Field(None, description="Reason code if skipped")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Translation completed",
                    "translation": "Hola mundo, esta es una solicitud de traducción de prueba.",
                    "score": 0.89,
                    "complexity_score": 0.12,
                    "detected_input_lang": "en"
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
