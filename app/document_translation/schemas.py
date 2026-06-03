from pydantic import BaseModel, Field
from typing import Any, Optional

class DocumentTranslationRequest(BaseModel):
    document_url: str = Field(..., description="The URL of the document file to translate")
    source_lang: str = Field(..., description="The source language code")
    target_lang: str = Field(..., description="The target language code")
    brand_uuid: Optional[str] = Field(default=None, description="Optional brand UUID for tone and glossary context")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "document_url": "https://example.com/sample.json",
                    "source_lang": "en",
                    "target_lang": "es",
                    "brand_uuid": "123e4567-e89b-12d3-a456-426614174000"
                }
            ]
        }
    }

class DocumentTranslationData(BaseModel):
    message: str = Field(..., description="Status message of the document translation processing")
    data: dict[str, Any] = Field(..., description="Echoed input payload or processing metadata")
    translated_document: Optional[Any] = Field(None, description="The fully translated document")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "translate document controller executed",
                    "data": {
                        "document_url": "https://example.com/sample.json",
                        "source_lang": "en",
                        "target_lang": "es"
                    },
                    "translated_document": None
                }
            ]
        }
    }
