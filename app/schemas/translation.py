from pydantic import BaseModel, Field
from typing import Any, Optional, Generic, TypeVar

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    success: bool = Field(..., description="Indicates if the request was successful")
    data: Optional[T] = Field(None, description="The response data payload if successful")
    error: Optional[str] = Field(None, description="Error message if the request failed")

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

class DocumentTranslationRequest(BaseModel):
    document_url: str = Field(..., description="The URL of the document file to translate")
    source_lang: str = Field(..., description="The source language code")
    target_lang: str = Field(..., description="The target language code")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "document_url": "https://example.com/sample.docx",
                    "source_lang": "en",
                    "target_lang": "es"
                }
            ]
        }
    }

class DocumentTranslationData(BaseModel):
    message: str = Field(..., description="Status message of the document translation processing")
    data: dict[str, Any] = Field(..., description="Echoed input payload or processing metadata")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "translate document controller executed",
                    "data": {
                        "document_url": "https://example.com/sample.docx",
                        "source_lang": "en",
                        "target_lang": "es"
                    }
                }
            ]
        }
    }
