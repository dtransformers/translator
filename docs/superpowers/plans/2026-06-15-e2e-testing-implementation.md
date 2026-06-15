# E2E Testing for CLI and Endpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a new end-to-end test suite (`tests/test_e2e.py`) to verify the translation CLI and all API endpoints.

**Architecture:** We use `typer.testing.CliRunner` to execute the CLI commands in-process and `httpx.AsyncClient` to test the API endpoints. Third-party integrations (DB, Duckling, models, LLM) are patched at the boundary layer.

**Tech Stack:** pytest, pytest-mock, pytest-asyncio, httpx, typer.

---

### Task 1: Create the E2E Test File

**Files:**
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Write E2E test suite file containing CLI and Endpoint tests**

Create the file `tests/test_e2e.py` with the following implementation:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
import typer
from typer.testing import CliRunner

from app.main import app
from app.text_translation.controller import TextTranslationController
from app.brands.models import Brand
from app.domains.models import Domain
from scripts.translate_json import app as cli_app


# ===================================================================== #
#  CLI E2E Tests
# ===================================================================== #

def test_cli_init_success(mocker):
    """Test the translator init command end-to-end under successful conditions."""
    mocker.patch("scripts.translate_json.init_db", new_callable=AsyncMock)
    
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    
    mock_begin = MagicMock()
    mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_begin.__aexit__ = AsyncMock()
    
    mocker.patch("scripts.translate_json.engine.begin", return_value=mock_begin)
    
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mocker.patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response)
    
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock()
    mocker.patch("scripts.translate_json.get_llm", return_value=mock_llm)
    
    mocker.patch("scripts.translate_json.nllb_service.preload_models", return_value=None)
    mocker.patch("scripts.translate_json.get_embedding_model", return_value=None)
    mocker.patch("scripts.translate_json._get_model", return_value=None)
    mocker.patch("scripts.translate_json.nltk.data.find", return_value=True)

    runner = CliRunner()
    result = runner.invoke(cli_app, ["init"])
    assert result.exit_code == 0
    assert "Init complete" in result.output


def test_cli_translate_success(tmp_path, mocker):
    """Test translating a JSON document via the CLI end-to-end."""
    input_file = tmp_path / "en.json"
    output_file = tmp_path / "ar.json"
    
    input_data = {"welcome": "Hello", "menu": {"title": "Main"}}
    input_file.write_text(json.dumps(input_data), encoding="utf-8")
    
    mocker.patch("scripts.translate_json.init_db", new_callable=AsyncMock)
    
    mock_translate_text = AsyncMock(side_effect=lambda payload, **kwargs: {"translation": f"TR_{payload.text}"})
    mocker.patch(
        "scripts.translate_json.TextTranslationController.translate_text",
        new=mock_translate_text
    )
    
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "translate",
            "-i", str(input_file),
            "-o", str(output_file),
            "-t", "ar",
            "-s", "en"
        ]
    )
    
    assert result.exit_code == 0
    assert "Successfully translated" in result.output
    
    assert output_file.exists()
    output_data = json.loads(output_file.read_text(encoding="utf-8"))
    assert output_data["welcome"] == "TR_Hello"
    assert output_data["menu"]["title"] == "TR_Main"


def test_cli_translate_missing_input(tmp_path):
    """Test CLI translate fails when the input file is missing."""
    output_file = tmp_path / "ar.json"
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "translate",
            "-i", "nonexistent.json",
            "-o", str(output_file),
            "-t", "ar"
        ]
    )
    assert result.exit_code == 1
    assert "does not exist" in result.output


# ===================================================================== #
#  Endpoint E2E Tests
# ===================================================================== #

@pytest.mark.asyncio
async def test_endpoint_health(client: AsyncClient, mocker):
    """Test health check route."""
    mocker.patch("app.main.health_status", {"db": "ok", "duckling": "ok", "models": "ok", "llm": "ok"})
    
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_endpoint_translate_success(client: AsyncClient, mocker):
    """Test translating text via translation route."""
    mocker.patch(
        "app.text_translation.router.TextTranslationController.translate_text",
        new_callable=AsyncMock,
        return_value={
            "translation": "Bonjour",
            "score": 0.9,
            "complexity_score": 20,
            "detected_input_lang": "en"
        }
    )
    response = await client.post(
        "/api/v1/translate",
        json={"text": "Hello", "source_lang": "en", "target_lang": "fr"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["translation"] == "Bonjour"


@pytest.mark.asyncio
async def test_endpoint_document_success(client: AsyncClient, mocker):
    """Test translating a document via document route."""
    mocker.patch(
        "app.document_translation.router.DocumentTranslationController.translate_document",
        new_callable=AsyncMock,
        return_value={
            "message": "Document translation completed successfully",
            "data": {
                "document_url": "https://example.com/doc.json",
                "source_lang": "en",
                "target_lang": "fr"
            },
            "translated_document": {"greeting": "Bonjour"}
        }
    )
    response = await client.post(
        "/api/v1/document",
        json={
            "document_url": "https://example.com/doc.json",
            "source_lang": "en",
            "target_lang": "fr"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["translated_document"]["greeting"] == "Bonjour"


@pytest.mark.asyncio
async def test_endpoint_brands_crud(client: AsyncClient, mocker):
    """Test CRUD operations on Brands endpoints."""
    mock_brand = Brand(
        id=1,
        uuid="123e4567-e89b-12d3-a456-426614174000",
        name="BrandName",
        industry="Tech",
        keywords=[],
        entities=[]
    )
    
    # Create
    mocker.patch(
        "app.brands.router.BrandController.create",
        new_callable=AsyncMock,
        return_value=mock_brand
    )
    create_resp = await client.post(
        "/api/v1/brands",
        json={"name": "BrandName", "industry": "Tech"}
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["data"]["uuid"] == "123e4567-e89b-12d3-a456-426614174000"

    # Get
    mocker.patch(
        "app.brands.router.BrandController.get_by_uuid",
        new_callable=AsyncMock,
        return_value=mock_brand
    )
    get_resp = await client.get("/api/v1/brands/123e4567-e89b-12d3-a456-426614174000")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["name"] == "BrandName"

    # Update
    mocker.patch(
        "app.brands.router.BrandController.update",
        new_callable=AsyncMock,
        return_value=mock_brand
    )
    put_resp = await client.put(
        "/api/v1/brands/123e4567-e89b-12d3-a456-426614174000",
        json={"name": "NewBrandName"}
    )
    assert put_resp.status_code == 200

    # Delete
    mocker.patch(
        "app.brands.router.BrandController.delete",
        new_callable=AsyncMock,
        return_value=True
    )
    del_resp = await client.delete("/api/v1/brands/123e4567-e89b-12d3-a456-426614174000")
    assert del_resp.status_code == 200


@pytest.mark.asyncio
async def test_endpoint_domains_crud(client: AsyncClient, mocker):
    """Test CRUD operations on Domains endpoints."""
    mock_domain = Domain(
        uuid="123e4567-e89b-12d3-a456-426614174001",
        name="ui",
        description="UI elements",
        content_types=["button"],
        rules={"creativity": "low"}
    )
    
    # Create
    mocker.patch(
        "app.domains.router.DomainController.get_by_name",
        new_callable=AsyncMock,
        return_value=None
    )
    mocker.patch(
        "app.domains.router.DomainController.create",
        new_callable=AsyncMock,
        return_value=mock_domain
    )
    create_resp = await client.post(
        "/api/v1/domains/",
        json={
            "name": "ui",
            "description": "UI elements",
            "content_types": ["button"],
            "rules": {"creativity": "low"}
        }
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["data"]["name"] == "ui"

    # List
    mocker.patch(
        "app.domains.router.DomainController.list_domains",
        new_callable=AsyncMock,
        return_value=[mock_domain]
    )
    list_resp = await client.get("/api/v1/domains/")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) == 1

    # Get
    mocker.patch(
        "app.domains.router.DomainController.get_by_name",
        new_callable=AsyncMock,
        return_value=mock_domain
    )
    get_resp = await client.get("/api/v1/domains/ui")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["uuid"] == "123e4567-e89b-12d3-a456-426614174001"

    # Update
    mocker.patch(
        "app.domains.router.DomainController.update",
        new_callable=AsyncMock,
        return_value=mock_domain
    )
    put_resp = await client.put(
        "/api/v1/domains/ui",
        json={"description": "New description"}
    )
    assert put_resp.status_code == 200

    # Delete
    mocker.patch(
        "app.domains.router.DomainController.delete",
        new_callable=AsyncMock,
        return_value=True
    )
    del_resp = await client.delete("/api/v1/domains/ui")
    assert del_resp.status_code == 200


@pytest.mark.asyncio
async def test_endpoint_review_start(client: AsyncClient, mocker):
    """Test triggering background review batch."""
    response = await client.post("/api/v1/review/start")
    assert response.status_code == 202
    data = response.json()
    assert data["success"] is True
    assert "started" in data["message"]
```

- [ ] **Step 2: Run new E2E tests to verify they all pass**

Run: `conda run -n translator python -m pytest tests/test_e2e.py -v`
Expected: 10 tests passed successfully.

- [ ] **Step 3: Run the entire test suite to ensure no regressions**

Run: `conda run -n translator python -m pytest`
Expected: 31 tests passed successfully.

- [ ] **Step 4: Commit the new E2E tests**

Run:
```bash
git add tests/test_e2e.py docs/superpowers/plans/2026-06-15-e2e-testing-implementation.md
git commit -m "feat: add CLI and Endpoint E2E test suite"
```
