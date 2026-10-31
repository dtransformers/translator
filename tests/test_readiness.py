import pytest
from httpx import AsyncClient

from app.main import app
from app.core.readiness import CheckStatus, Readiness, readiness, require_ready


def _all_ok() -> dict:
    return {name: CheckStatus(ok=True, error=None) for name in Readiness.CHECKS}


@pytest.fixture
def gated(client: AsyncClient):
    """Use the real readiness gate instead of the conftest override."""
    app.dependency_overrides.pop(require_ready, None)
    return client


@pytest.mark.asyncio
async def test_translate_rejected_when_one_check_fails(gated: AsyncClient, mocker):
    checks = _all_ok()
    checks["llm"] = CheckStatus(ok=False, error="ConnectError: connection refused")
    mocker.patch.dict(readiness.checks, checks)

    response = await gated.post(
        "/api/v1/translate", json={"text": "Hello", "source_lang": "en", "target_lang": "fr"}
    )

    assert response.status_code == 503
    assert response.headers["retry-after"]
    body = response.json()
    assert body["success"] is False
    assert "llm: ConnectError: connection refused" in body["error"]


@pytest.mark.asyncio
async def test_translate_allowed_when_all_checks_pass(gated: AsyncClient, mocker):
    mocker.patch.dict(readiness.checks, _all_ok())
    mocker.patch(
        "app.text_translation.router.TextTranslationController.translate_text",
        return_value={"message": "Translation completed", "translation": "Bonjour", "score": 0.9, "complexity_score": 5},
    )

    response = await gated.post(
        "/api/v1/translate", json={"text": "Hello", "source_lang": "en", "target_lang": "fr"}
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_brand_routes_stay_open_when_not_ready(gated: AsyncClient, mocker):
    checks = _all_ok()
    checks["nllb"] = CheckStatus(ok=False, error="loading")
    mocker.patch.dict(readiness.checks, checks)
    mocker.patch("app.brands.router.BrandController.get_all", return_value=[])

    response = await gated.get("/api/v1/brands")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_reports_each_component(gated: AsyncClient, mocker):
    checks = _all_ok()
    checks["duckling"] = CheckStatus(ok=False, error="HTTPStatusError: 500")
    mocker.patch.dict(readiness.checks, checks)

    response = await gated.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["components"]["duckling"] == {"status": "error", "error": "HTTPStatusError: 500", "checked_at": None}
    assert body["components"]["db"]["status"] == "ok"


@pytest.mark.asyncio
async def test_liveness_ignores_readiness(gated: AsyncClient, mocker):
    mocker.patch.dict(readiness.checks, {name: CheckStatus() for name in Readiness.CHECKS})

    response = await gated.get("/health/live")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_monitor_recovers_after_outage(mocker):
    r = Readiness()
    for name in ("nllb", "embedding_model", "quality_model", "complexity_models", "nltk_punkt"):
        mocker.patch.object(r, f"_load_{name}", return_value=None)
    mocker.patch.object(r, "_check_db", return_value=None)
    mocker.patch.object(r, "_check_duckling", return_value=None)
    llm = mocker.patch.object(r, "_check_llm", side_effect=RuntimeError("model 'x' is not installed in Ollama"))

    await r.check_services()
    await r.load_models()
    assert not r.is_ready
    assert r.failing() == {"llm": "RuntimeError: model 'x' is not installed in Ollama"}

    llm.side_effect = None
    await r.check_services()
    assert r.is_ready
