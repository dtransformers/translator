from unittest.mock import AsyncMock, MagicMock

import pytest

from app.text_translation.models import Translation
from app.text_translation.service import TranslationService
from app.text_translation.schemas import TranslationSource


@pytest.mark.asyncio
@pytest.mark.parametrize("cached_body,distance,cached_normalized,expected_hit", [
    ("three", 0.001, "we can use number_0 approaches", True),
    ("four", 0.001, "we can use number_0 approaches", False),
    (None, 0.001, "we can use approaches", False),
    ("three", 0.1, "we can use number_0 approaches", False),
    ("three", 0.001, "we cannot use number_0 approaches", False),
])
async def test_semantic_cache_reuses_only_matching_entities(mocker, cached_body, distance, cached_normalized, expected_hit):
    text = "We can use these three approaches"
    cached_text = "We can use three approaches"
    normalized = "we can use these number_0 approaches"
    candidate = Translation(value=cached_text, translation="Trois approches", normalized_text=cached_normalized)
    db = AsyncMock()
    result = MagicMock()
    result.first.return_value = (candidate, distance)
    db.execute.return_value = result
    svc = TranslationService(db)
    mocker.patch.object(svc, "_find_l1_exact", return_value=None)
    mocker.patch.object(svc, "_find_l2_normalized", return_value=None)
    mocker.patch("app.text_translation.service.get_embedding", return_value=[0.1, 0.2])

    async def abstract(value, language):
        if value == text:
            return normalized, [{"dim": "number", "body": "three", "start": 17, "end": 22}]
        assert value == cached_text
        entities = [{"dim": "number", "body": cached_body, "start": 11, "end": 16}] if cached_body else []
        return candidate.normalized_text, entities

    mocker.patch("app.text_translation.service.abstract_entities", side_effect=abstract)
    hit = await svc.find_cached(text, "en", "fr")
    if expected_hit:
        assert hit == (candidate, TranslationSource.SEMANTIC_CACHE)
    else:
        assert hit is None
