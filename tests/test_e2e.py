import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient
from typer.testing import CliRunner

from app.brands.models import Brand
from app.domains.models import Domain
from scripts.translate_json import app as cli_app


# ===================================================================== #
#  CLI E2E Tests
# ===================================================================== #

def test_cli_init_success(mocker):
    """Test the translator init command end-to-end under successful conditions."""
    mock_init_db = mocker.patch("scripts.translate_json.init_db", new_callable=AsyncMock)
    
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    
    mock_begin = MagicMock()
    mock_begin.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_begin.__aexit__ = AsyncMock()
    
    mock_engine = MagicMock()
    mock_engine.begin = MagicMock(return_value=mock_begin)
    mocker.patch("scripts.translate_json.engine", mock_engine)
    
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_http_post = mocker.patch(
        "httpx.AsyncClient.post", 
        new_callable=AsyncMock, 
        return_value=mock_response
    )
    
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock()
    mocker.patch("app.llms.model.get_llm", return_value=mock_llm)
    
    mocker.patch("app.machine_translation.nllb_service.NLLBService.preload_models", return_value=None)
    mocker.patch("app.pipeline.embeddings.get_embedding_model", return_value=None)
    mocker.patch("app.pipeline.quality._get_model", return_value=None)
    mocker.patch("nltk.data.find", return_value=True)

    runner = CliRunner()
    result = runner.invoke(cli_app, ["init"])
    assert result.exit_code == 0
    assert "Init complete" in result.output
    
    # Assert mock invocations
    mock_init_db.assert_called_once()
    mock_http_post.assert_called_once()
    mock_llm.ainvoke.assert_called_once_with("ping")


def test_cli_translate_success(tmp_path, mocker):
    """Test translating a JSON document via the CLI end-to-end."""
    input_file = tmp_path / "en.json"
    output_file = tmp_path / "ar.json"
    
    input_data = {"welcome": "Hello", "menu": {"title": "Main"}}
    input_file.write_text(json.dumps(input_data), encoding="utf-8")
    
    mocker.patch("scripts.translate_json.init_db", new_callable=AsyncMock)
    
    mock_translate_text = AsyncMock(
        side_effect=lambda payload, **kwargs: {"translation": f"TR_{payload.text}"}
    )
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
    
    assert mock_translate_text.call_count == 2


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
    mocker.patch(
        "app.main.health_status",
        {"db": "ok", "duckling": "ok", "models": "ok", "llm": "ok"}
    )
    
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_endpoint_translate_success(client: AsyncClient, mocker):
    """Test translating text via translation route."""
    mock_translate = mocker.patch(
        "app.text_translation.router.TextTranslationController.translate_text",
        new_callable=AsyncMock,
        return_value={
            "message": "Translation completed",
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
    mock_translate.assert_called_once()


@pytest.mark.asyncio
async def test_endpoint_document_success(client: AsyncClient, mocker):
    """Test translating a document via document route."""
    mock_translate_doc = mocker.patch(
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
    mock_translate_doc.assert_called_once()


# ===================================================================== #
#  Brand CRUD Endpoint Tests
# ===================================================================== #

@pytest.fixture
def mock_brand():
    return Brand(
        id=1,
        uuid="123e4567-e89b-12d3-a456-426614174000",
        name="BrandName",
        industry="Tech",
        keywords=[],
        entities=[]
    )


@pytest.mark.asyncio
async def test_endpoint_create_brand(client: AsyncClient, mock_brand, mocker):
    mock_create = mocker.patch(
        "app.brands.router.BrandController.create",
        new_callable=AsyncMock,
        return_value=mock_brand
    )
    response = await client.post(
        "/api/v1/brands",
        json={"name": "BrandName", "industry": "Tech"}
    )
    assert response.status_code == 201
    assert response.json()["data"]["uuid"] == "123e4567-e89b-12d3-a456-426614174000"
    mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_endpoint_get_brand(client: AsyncClient, mock_brand, mocker):
    mock_get = mocker.patch(
        "app.brands.router.BrandController.get_by_uuid",
        new_callable=AsyncMock,
        return_value=mock_brand
    )
    response = await client.get("/api/v1/brands/123e4567-e89b-12d3-a456-426614174000")
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "BrandName"
    mock_get.assert_called_once_with("123e4567-e89b-12d3-a456-426614174000")


@pytest.mark.asyncio
async def test_endpoint_update_brand(client: AsyncClient, mock_brand, mocker):
    mock_update = mocker.patch(
        "app.brands.router.BrandController.update",
        new_callable=AsyncMock,
        return_value=mock_brand
    )
    response = await client.put(
        "/api/v1/brands/123e4567-e89b-12d3-a456-426614174000",
        json={"name": "NewBrandName"}
    )
    assert response.status_code == 200
    mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_endpoint_delete_brand(client: AsyncClient, mocker):
    mock_delete = mocker.patch(
        "app.brands.router.BrandController.delete",
        new_callable=AsyncMock,
        return_value=True
    )
    response = await client.delete("/api/v1/brands/123e4567-e89b-12d3-a456-426614174000")
    assert response.status_code == 200
    mock_delete.assert_called_once_with("123e4567-e89b-12d3-a456-426614174000")


# ===================================================================== #
#  Domain CRUD Endpoint Tests
# ===================================================================== #

@pytest.fixture
def mock_domain():
    return Domain(
        uuid="123e4567-e89b-12d3-a456-426614174001",
        name="ui",
        description="UI elements",
        content_types=["button"],
        rules={"creativity": "low"}
    )


@pytest.mark.asyncio
async def test_endpoint_create_domain(client: AsyncClient, mock_domain, mocker):
    mocker.patch(
        "app.domains.router.DomainController.get_by_name",
        new_callable=AsyncMock,
        return_value=None
    )
    mock_create = mocker.patch(
        "app.domains.router.DomainController.create",
        new_callable=AsyncMock,
        return_value=mock_domain
    )
    response = await client.post(
        "/api/v1/domains/",
        json={
            "name": "ui",
            "description": "UI elements",
            "content_types": ["button"],
            "rules": {"creativity": "low"}
        }
    )
    assert response.status_code == 201
    assert response.json()["data"]["name"] == "ui"
    mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_endpoint_list_domains(client: AsyncClient, mock_domain, mocker):
    mock_list = mocker.patch(
        "app.domains.router.DomainController.list_domains",
        new_callable=AsyncMock,
        return_value=[mock_domain]
    )
    response = await client.get("/api/v1/domains/")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    mock_list.assert_called_once()


@pytest.mark.asyncio
async def test_endpoint_get_domain(client: AsyncClient, mock_domain, mocker):
    mock_get = mocker.patch(
        "app.domains.router.DomainController.get_by_name",
        new_callable=AsyncMock,
        return_value=mock_domain
    )
    response = await client.get("/api/v1/domains/ui")
    assert response.status_code == 200
    assert response.json()["data"]["uuid"] == "123e4567-e89b-12d3-a456-426614174001"
    mock_get.assert_called_once_with("ui")


@pytest.mark.asyncio
async def test_endpoint_update_domain(client: AsyncClient, mock_domain, mocker):
    mock_update = mocker.patch(
        "app.domains.router.DomainController.update",
        new_callable=AsyncMock,
        return_value=mock_domain
    )
    response = await client.put(
        "/api/v1/domains/ui",
        json={"description": "New description"}
    )
    assert response.status_code == 200
    mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_endpoint_delete_domain(client: AsyncClient, mocker):
    mock_delete = mocker.patch(
        "app.domains.router.DomainController.delete",
        new_callable=AsyncMock,
        return_value=True
    )
    response = await client.delete("/api/v1/domains/ui")
    assert response.status_code == 200
    mock_delete.assert_called_once_with("ui")


# ===================================================================== #
#  Reviewer & Security Endpoint Tests
# ===================================================================== #

@pytest.mark.asyncio
async def test_endpoint_review_start(client: AsyncClient, mocker):
    """Test triggering background review batch without real DB execution."""
    mock_add_task = mocker.patch("fastapi.BackgroundTasks.add_task")
    
    response = await client.post("/api/v1/review/start")
    assert response.status_code == 202
    data = response.json()
    assert data["success"] is True
    assert "started" in data["message"]
    mock_add_task.assert_called_once()


@pytest.mark.asyncio
async def test_endpoint_unauthorized(client: AsyncClient):
    """Test endpoints reject requests with invalid/missing authorization."""
    client.auth = None
    
    response = await client.post(
        "/api/v1/translate",
        json={"text": "Hello", "source_lang": "en", "target_lang": "fr"}
    )
    assert response.status_code == 401
    assert response.json()["success"] is False


@pytest.mark.asyncio
async def test_endpoint_translate_validation_error(client: AsyncClient):
    """Test translation endpoint rejects requests with missing fields."""
    response = await client.post(
        "/api/v1/translate",
        json={"text": "Hello"}
    )
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "Validation error" in data["error"]
