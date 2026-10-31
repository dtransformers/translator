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
        "app.text_translation.controller.TranslationService.create",
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
        "app.text_translation.controller.TranslationService.find_cached",
        new_callable=AsyncMock,
        return_value=None,
    )
    mocker.patch(
        "app.text_translation.controller.BrandService.get_brand_context",
        new_callable=AsyncMock,
        return_value={},
    )
    mocker.patch(
        "app.text_translation.controller.ReusableUnitService.build_glossary_from_units",
        new_callable=AsyncMock,
        return_value={},
    )
    mocker.patch(
        "app.text_translation.controller.DomainService.get_by_name",
        new_callable=AsyncMock,
        return_value=mock_domain,
    )
    mocker.patch(
        "app.text_translation.controller.translate",
        new_callable=AsyncMock,
        return_value="Save",
    )
    mocker.patch(
        "app.text_translation.controller.score_translation",
        return_value=0.95,
    )
    mocker.patch(
        "app.text_translation.controller.TranslationService.save_with_cache_fields",
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



def _patch_fresh_pipeline(mocker, translate_mock):
    mocker.patch(
        "app.text_translation.controller.TranslationService.find_cached",
        new_callable=AsyncMock,
        return_value=None,
    )
    mocker.patch(
        "app.text_translation.controller.BrandService.get_brand_context",
        new_callable=AsyncMock,
        return_value={},
    )
    mocker.patch(
        "app.text_translation.controller.ReusableUnitService.build_glossary_from_units",
        new_callable=AsyncMock,
        return_value={},
    )
    mocker.patch(
        "app.text_translation.controller.calculate_complexity_score",
        new_callable=AsyncMock,
        return_value=12,
    )
    mocker.patch("app.text_translation.controller.translate", translate_mock)
    mocker.patch(
        "app.text_translation.controller.score_translation",
        return_value=0.91,
    )
    mocker.patch(
        "app.text_translation.controller.TranslationService.save_with_cache_fields",
        new_callable=AsyncMock,
    )


@pytest.mark.asyncio
async def test_translate_text_fresh_response_shape(client: AsyncClient, mocker):
    _patch_fresh_pipeline(mocker, AsyncMock(return_value="Bonjour le monde"))

    response = await client.post("/api/v1/translate", json={
        "text": "Hello world",
        "source_lang": "en",
        "target_lang": "fr",
    })

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["complexity_score"] == 12
    assert isinstance(data["complexity_score"], int)
    assert data["cached"] is False
    assert data["skipped"] is False
    assert data["reason"] is None


@pytest.mark.asyncio
async def test_translate_text_engine_failure_returns_error(client: AsyncClient, mocker):
    _patch_fresh_pipeline(mocker, AsyncMock(side_effect=RuntimeError("LLM timed out")))

    response = await client.post("/api/v1/translate", json={
        "text": "Hello world",
        "source_lang": "en",
        "target_lang": "fr",
    })

    assert response.status_code == 502
    data = response.json()
    assert data["success"] is False
    assert data["data"] is None
    assert "LLM timed out" in data["error"]


@pytest.mark.asyncio
async def test_translate_text_cache_hit_uses_stored_complexity(client: AsyncClient, mocker):
    from app.text_translation.models import Translation

    cached = Translation(
        translation="Bonjour le monde",
        score=0.93,
        trust_score=0.93,
        complexity_score=37,
        detected_input_lang="en",
    )
    mocker.patch(
        "app.text_translation.controller.TranslationService.find_cached",
        new_callable=AsyncMock,
        return_value=cached,
    )
    complexity = mocker.patch(
        "app.text_translation.controller.calculate_complexity_score",
        new_callable=AsyncMock,
    )

    response = await client.post("/api/v1/translate", json={
        "text": "Hello world",
        "source_lang": "en",
        "target_lang": "fr",
    })

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["cached"] is True
    assert data["complexity_score"] == 37
    complexity.assert_not_called()
