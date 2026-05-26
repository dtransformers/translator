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
    # Mock the TranslationRepository.create_translation to avoid real DB queries
    mocker.patch("app.controllers.translation_controller.TranslationRepository.create_translation", new_callable=AsyncMock)
    
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
