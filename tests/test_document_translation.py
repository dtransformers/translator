import pytest
from httpx import AsyncClient, HTTPStatusError, Request, Response
from unittest.mock import AsyncMock, patch

from app.pipeline.document import (
    json_to_ast,
    collect_translatable_nodes,
    DocumentNode,
    TextNode,
)
from app.controllers.translation_controller import translate_document_controller
from app.schemas.translation import DocumentTranslationRequest


def test_json_to_ast_and_back():
    sample_json = {
        "title": "Welcome to our website",
        "description": "This is a simple template for ordering.",
        "icon": "home-icon.png",
        "nested": {
            "label": "Click here",
            "count": 42,
            "items": [
                {"name": "Apples", "icons": "apple-icon.png"},
                {"name": "Oranges", "icons": "orange-icon.png"}
            ]
        },
        "is_active": True,
        "price": 10.99,
        "empty": None
    }

    # Parse to AST
    root_node = json_to_ast(sample_json)
    doc_node = DocumentNode(root_node, "json")

    # Verify translatable nodes collected
    translatable_nodes = collect_translatable_nodes(doc_node)

    # Expected translatable fields: title, description, nested.label, nested.items[0].name, nested.items[1].name
    # count, is_active, price, empty are primitives/ValueNodes.
    # icon, nested.items[0].icons, nested.items[1].icons should be marked as is_translatable=False.
    translatable_paths = [node.path for node in translatable_nodes]
    assert "title" in translatable_paths
    assert "description" in translatable_paths
    assert "nested.label" in translatable_paths
    assert "nested.items[0].name" in translatable_paths
    assert "nested.items[1].name" in translatable_paths

    # Confirm icon keys are not in the translatable nodes
    assert "icon" not in translatable_paths
    assert "nested.items[0].icons" not in translatable_paths
    assert "nested.items[1].icons" not in translatable_paths

    # Set translations on nodes
    for node in translatable_nodes:
        node.translated_value = f"TRANSLATED_{node.value}"

    # Reconstitute and verify dict structure is preserved
    translated_json = doc_node.to_dict()
    
    assert translated_json["title"] == "TRANSLATED_Welcome to our website"
    assert translated_json["description"] == "TRANSLATED_This is a simple template for ordering."
    assert translated_json["icon"] == "home-icon.png"  # Preserved
    assert translated_json["nested"]["label"] == "TRANSLATED_Click here"
    assert translated_json["nested"]["count"] == 42  # Preserved
    assert translated_json["nested"]["items"][0]["name"] == "TRANSLATED_Apples"
    assert translated_json["nested"]["items"][0]["icons"] == "apple-icon.png"  # Preserved
    assert translated_json["nested"]["items"][1]["name"] == "TRANSLATED_Oranges"
    assert translated_json["nested"]["items"][1]["icons"] == "orange-icon.png"  # Preserved
    assert translated_json["is_active"] is True  # Preserved
    assert translated_json["price"] == 10.99  # Preserved
    assert translated_json["empty"] is None  # Preserved


@pytest.mark.asyncio
async def test_translate_document_controller_success(mocker):
    # Mock database session
    db_mock = AsyncMock()

    # Mock external GET response for the JSON document
    document_data = {
        "title": "Hello world",
        "icon": "icon.png",
        "nested": {
            "text": "Press save"
        }
    }
    
    # Mock httpx GET
    mock_response = Response(200, json=document_data)
    mocker.patch("httpx.AsyncClient.get", return_value=mock_response)

    # Mock translate_text_controller
    async def mock_translate_text(payload, db, brand_uuid, domain_name, filename, property_name):
        return {"translation": f"ES_{payload.text}"}

    mocker.patch(
        "app.controllers.translation_controller.translate_text_controller",
        side_effect=mock_translate_text
    )

    request_payload = DocumentTranslationRequest(
        document_url="https://example.com/sample.json",
        source_lang="en",
        target_lang="es"
    )

    result = await translate_document_controller(
        payload=request_payload,
        db=db_mock,
        brand_uuid=None,
        domain_name=None
    )

    assert "error" not in result
    assert result["message"] == "Document translation completed successfully"
    assert result["data"]["document_url"] == "https://example.com/sample.json"
    assert result["translated_document"]["title"] == "ES_Hello world"
    assert result["translated_document"]["icon"] == "icon.png"  # Key 'icon' skipped
    assert result["translated_document"]["nested"]["text"] == "ES_Press save"


@pytest.mark.asyncio
async def test_translate_document_controller_unsupported_languages(mocker):
    db_mock = AsyncMock()
    request_payload = DocumentTranslationRequest(
        document_url="https://example.com/sample.json",
        source_lang="en",
        target_lang="jp"  # Japanese is unsupported
    )

    result = await translate_document_controller(
        payload=request_payload,
        db=db_mock
    )

    assert "error" in result
    assert "Language pair en->jp is not supported" in result["error"]


@pytest.mark.asyncio
async def test_translate_document_controller_http_failure(mocker):
    db_mock = AsyncMock()
    
    # Mock httpx GET error
    request = Request("GET", "https://example.com/notfound.json")
    mock_response = Response(404, request=request)
    mocker.patch("httpx.AsyncClient.get", side_effect=HTTPStatusError("404 Client Error", request=request, response=mock_response))

    request_payload = DocumentTranslationRequest(
        document_url="https://example.com/notfound.json",
        source_lang="en",
        target_lang="es"
    )

    result = await translate_document_controller(
        payload=request_payload,
        db=db_mock
    )

    assert "error" in result
    assert "Failed to fetch document" in result["error"]


@pytest.mark.asyncio
async def test_translate_document_endpoint_integration(client: AsyncClient, mocker):
    document_data = {
        "hello": "Hello"
    }
    
    # Mock GET response
    mock_response = Response(200, json=document_data)
    mocker.patch("httpx.AsyncClient.get", return_value=mock_response)

    # Mock translate_text_controller
    mocker.patch(
        "app.controllers.translation_controller.translate_text_controller",
        return_value={"translation": "Hola"}
    )

    response = await client.post(
        "/api/v1/document",
        json={
            "document_url": "https://example.com/doc.json",
            "source_lang": "en",
            "target_lang": "es"
        }
    )

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["data"]["translated_document"]["hello"] == "Hola"


@pytest.mark.asyncio
async def test_translate_text_controller_cache_hit_fields(mocker):
    from app.translations.models import Translation
    from app.schemas.translation import TranslationRequest
    from app.controllers.translation_controller import translate_text_controller

    db_mock = AsyncMock()
    mock_translation = Translation(
        value="Hello world",
        translation="Hola mundo",
        score=0.95,
        detected_input_lang="en"
    )

    mocker.patch(
        "app.controllers.translation_controller.TranslationService.find_cached",
        return_value=mock_translation
    )

    payload = TranslationRequest(
        text="Hello world",
        source_lang="en",
        target_lang="es"
    )

    result = await translate_text_controller(payload, db=db_mock)
    assert result["cached"] is True
    assert result["translation"] == "Hola mundo"
    assert result["score"] == 0.95
    assert "complexity_score" in result
    assert result["detected_input_lang"] == "en"


@pytest.mark.asyncio
async def test_translate_text_controller_llm_rag_lookup(mocker):
    from app.translations.models import Translation
    from app.schemas.translation import TranslationRequest
    from app.controllers.translation_controller import translate_text_controller

    db_mock = AsyncMock()
    
    # 1. No cache hit
    mocker.patch(
        "app.controllers.translation_controller.TranslationService.find_cached",
        return_value=None
    )

    # 2. Similar RAG examples from DB
    similar_record = Translation(
        value="Hello world!",
        translation="¡Hola mundo!"
    )
    mocker.patch(
        "app.controllers.translation_controller.TranslationService.retrieve_similar_translations",
        return_value=[similar_record]
    )

    # 3. Mock other services
    mocker.patch(
        "app.controllers.translation_controller.BrandService.get_brand_context",
        return_value={}
    )
    mocker.patch(
        "app.controllers.translation_controller.TranslationService.build_glossary_from_units",
        return_value={}
    )
    mocker.patch(
        "app.controllers.translation_controller.TranslationService.save_with_cache_fields"
    )
    mocker.patch(
        "app.controllers.translation_controller.score_translation",
        return_value=0.9
    )

    # Mock the translate function to check similar_examples argument
    mock_translate = AsyncMock(return_value="Hola mundito")
    mocker.patch(
        "app.controllers.translation_controller.translate",
        new=mock_translate
    )

    # Ensure complexity triggers LLM (>= 50)
    mocker.patch(
        "app.controllers.translation_controller.calculate_complexity_score",
        return_value=60
    )

    payload = TranslationRequest(
        text="Hello world!",
        source_lang="en",
        target_lang="es"
    )

    result = await translate_text_controller(payload, db=db_mock)
    
    assert result["translation"] == "Hola mundito"
    # Verify mock_translate was called with the RAG example
    mock_translate.assert_called_once()
    kwargs = mock_translate.call_args[1]
    assert "similar_examples" in kwargs
    assert len(kwargs["similar_examples"]) == 1
    assert kwargs["similar_examples"][0]["source"] == "Hello world!"
    assert kwargs["similar_examples"][0]["translation"] == "¡Hola mundo!"
