import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_translate_text_missing_fields(client: AsyncClient):
    response = await client.post("/api/v1/translate", json={
        "text": "Hello"
    })

    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert "source_lang" in data["error"]


@pytest.mark.asyncio
async def test_translate_text_untranslatable(client: AsyncClient, mocker):
    # Mock the TranslationService.create to avoid real DB queries
    mocker.patch(
        "app.controllers.translation_controller.TranslationService.create",
        new_callable=AsyncMock,
    )

    response = await client.post("/api/v1/translate", json={
        "text": "/href",
        "source_lang": "en",
        "target_lang": "es"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["translation"] == "/href"
    assert data["data"]["skipped"] is True
    assert data["data"]["reason"] == "not_translatable"


@pytest.mark.asyncio
async def test_translate_text_with_domain(client: AsyncClient, mocker):
    from app.domains.models import Domain

    mock_domain = Domain(
        uuid="domain-uuid-123",
        name="ui",
        description="UI elements",
        content_types=["button"],
        rules={
            "creativity": "low",
            "preserve_placeholders": True,
            "strict_glossary": True,
            "brevity_required": True,
            "cache_priority": "high",
        },
    )

    mocker.patch(
        "app.controllers.translation_controller.TranslationService.find_cached",
        new_callable=AsyncMock,
        return_value=None,
    )
    mocker.patch(
        "app.controllers.translation_controller.BrandService.get_brand_context",
        new_callable=AsyncMock,
        return_value={},
    )
    mocker.patch(
        "app.controllers.translation_controller.TranslationService.build_glossary_from_units",
        new_callable=AsyncMock,
        return_value={},
    )
    mocker.patch(
        "app.controllers.translation_controller.DomainService.get_by_name",
        new_callable=AsyncMock,
        return_value=mock_domain,
    )
    mocker.patch(
        "app.controllers.translation_controller.translate",
        new_callable=AsyncMock,
        return_value="Save",
    )
    mocker.patch(
        "app.controllers.translation_controller.score_translation",
        return_value=0.95,
    )
    mocker.patch(
        "app.controllers.translation_controller.TranslationService.save_with_cache_fields",
        new_callable=AsyncMock,
    )

    response = await client.post(
        "/api/v1/translate",
        params={"name": "ui"},
        json={
            "text": "Save",
            "source_lang": "en",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["translation"] == "Save"
    assert data["data"]["score"] == 0.95

