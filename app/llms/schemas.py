"""Schemas sent to native decoding and used to validate generated translations."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, create_model


class TranslationResult(BaseModel):
    """A single translated text, with no surrounding commentary."""

    model_config = ConfigDict(extra="forbid", strict=True)
    translation: str


class GlossaryEntry(BaseModel):
    """One source term and its required translation."""

    model_config = ConfigDict(extra="forbid", strict=True)
    source: str = Field(description="Term as it appears in the source text")
    target: str = Field(description="Required translation of the term")


class FileSummary(BaseModel):
    """Short summary of a file, used as translation context."""

    model_config = ConfigDict(extra="forbid", strict=True)
    summary: str = Field(description="One short paragraph, no formatting")


class TranslationContext(BaseModel):
    """Translation context extracted from a single file."""

    model_config = ConfigDict(extra="forbid", strict=True)
    industry: str
    tone: str
    audience: str
    keywords: list[str]
    entities: list[str] = Field(description="Names that must not be translated, such as brands or products")
    glossary: list[GlossaryEntry]


class GlobalTranslationContext(TranslationContext):
    """Translation context merged across several files."""

    summary: str


class RefinedTranslations(BaseModel):
    """Refined drafts, in the same order as the input drafts."""

    model_config = ConfigDict(extra="forbid", strict=True)
    translations: list[str]


class TranslationValidation(BaseModel):
    """QA verdict for one translation."""

    model_config = ConfigDict(extra="forbid", strict=True)
    is_valid: bool
    error_type: Literal["meaning", "fluency", "structure", "placeholder", "none"]
    reason: str = Field(description="Short explanation in English")


class FixedTranslation(BaseModel):
    """Corrected translation, with no surrounding commentary."""

    model_config = ConfigDict(extra="forbid", strict=True)
    corrected_translation: str


class ComplexityRating(BaseModel):
    """Translation complexity of a text."""

    model_config = ConfigDict(extra="forbid", strict=True)
    score: int = Field(ge=0, le=100, description="0 is trivial, 100 is highly complex")


def translation_batch_schema(texts: dict[str, str]) -> type[BaseModel]:
    """Require exactly the input paths, each with a translated string value."""
    # Internal field names avoid collisions with Pydantic methods and private fields.
    return create_model(
        "TranslationBatch",
        __config__=ConfigDict(extra="forbid", strict=True),
        **{
            f"text_{index}": (str, Field(alias=path))
            for index, path in enumerate(texts)
        },
    )
