"""Brand-name masking/restoration around translation (issue #14)."""
from unittest.mock import AsyncMock

import pytest

from app.text_translation.controller import (
    BRAND_PLACEHOLDER,
    TextTranslationController,
    mask_brand,
    restore_brand,
)


def test_mask_brand_replaces_whole_word_case_insensitive():
    assert mask_brand("Buy ACME now, acme rocks", "Acme") == (
        f"Buy {BRAND_PLACEHOLDER} now, {BRAND_PLACEHOLDER} rocks"
    )
    # Not inside other words
    assert mask_brand("Acmetech", "Acme") == "Acmetech"


@pytest.mark.parametrize(
    "model_output",
    [
        "Achetez {{BRAND_NAME}} maintenant",
        "Achetez {{ BRAND_NAME }} maintenant",
        "Achetez {{brand_name}} maintenant",
        "Achetez {BRAND_NAME} maintenant",
        "Achetez { Brand_Name } maintenant",
    ],
)
def test_restore_brand_tolerates_placeholder_variants(model_output):
    assert restore_brand(model_output, "Acme") == "Achetez Acme maintenant"


def test_restore_brand_returns_none_when_placeholder_is_mangled():
    # Model split/translated the token; we cannot restore it safely.
    assert restore_brand("Achetez {{BRAND NAME}} maintenant", "Acme") is None
    assert restore_brand("Achetez BRAND_NAME maintenant", "Acme") is None


def test_restore_brand_leaves_text_without_placeholder_untouched():
    assert restore_brand("Achetez maintenant", "Acme") == "Achetez maintenant"


@pytest.mark.asyncio
async def test_execute_translation_restores_spaced_placeholder(mocker):
    translate_mock = AsyncMock(return_value="Achetez {{ BRAND_NAME }} maintenant")
    mocker.patch("app.text_translation.controller.translate", translate_mock)
    controller = TextTranslationController(db=None)

    text, ok, notes = await controller._execute_translation(
        "Buy Acme now", "en", "fr", 10, {"name": "Acme"}, {}, [],
    )

    assert translate_mock.await_args.args[0] == f"Buy {BRAND_PLACEHOLDER} now"
    assert (text, ok, notes) == ("Achetez Acme maintenant", True, None)


@pytest.mark.asyncio
async def test_execute_translation_fails_when_placeholder_cannot_be_restored(mocker):
    mocker.patch(
        "app.text_translation.controller.translate",
        AsyncMock(return_value="Achetez BRAND_NAME maintenant"),
    )
    controller = TextTranslationController(db=None)

    text, ok, notes = await controller._execute_translation(
        "Buy Acme now", "en", "fr", 10, {"name": "Acme"}, {}, [],
    )

    assert text is None
    assert ok is False
    assert "placeholder" in notes.lower()
