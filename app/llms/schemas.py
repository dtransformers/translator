"""Schemas sent to native decoding and used to validate generated translations."""
from pydantic import BaseModel, ConfigDict, Field, create_model


class TranslationResult(BaseModel):
    """A single translated text, with no surrounding commentary."""

    model_config = ConfigDict(extra="forbid", strict=True)
    translation: str


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
