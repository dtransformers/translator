import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from app.domains.models import Domain


@pytest.mark.asyncio
async def test_create_domain(client: AsyncClient, mocker):
    mock_domain = Domain(
        uuid="test-uuid-123",
        name="test-domain",
        description="A test domain description",
        content_types=["button", "label"],
        rules={
            "creativity": "low",
            "preserve_placeholders": True,
            "strict_glossary": True,
            "brevity_required": True,
            "cache_priority": "high",
        },
    )
    mocker.patch(
        "app.domains.controller.DomainService.get_by_name",
        new_callable=AsyncMock,
        return_value=None,
    )
    mocker.patch(
        "app.domains.controller.DomainService.create",
        new_callable=AsyncMock,
        return_value=mock_domain,
    )

    response = await client.post(
        "/api/v1/domains/",
        json={
            "name": "test-domain",
            "description": "A test domain description",
            "content_types": ["button", "label"],
            "rules": {
                "creativity": "low",
                "preserve_placeholders": True,
                "strict_glossary": True,
                "brevity_required": True,
                "cache_priority": "high",
            },
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "test-domain"
    assert data["data"]["rules"]["creativity"] == "low"


@pytest.mark.asyncio
async def test_create_domain_already_exists(client: AsyncClient, mocker):
    mock_domain = Domain(
        uuid="test-uuid-123",
        name="test-domain",
        description="A test domain description",
        content_types=["button", "label"],
        rules={"creativity": "low"},
    )
    mocker.patch(
        "app.domains.controller.DomainService.get_by_name",
        new_callable=AsyncMock,
        return_value=mock_domain,
    )

    response = await client.post(
        "/api/v1/domains/",
        json={
            "name": "test-domain",
            "rules": {"creativity": "low"},
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "already exists" in data["error"]


@pytest.mark.asyncio
async def test_list_domains(client: AsyncClient, mocker):
    mock_domains = [
        Domain(
            uuid="uuid-1",
            name="ui",
            description="UI domain",
            content_types=["button"],
            rules={"creativity": "low"},
        ),
        Domain(
            uuid="uuid-2",
            name="marketing",
            description="Marketing domain",
            content_types=["ad_copy"],
            rules={"creativity": "high"},
        ),
    ]
    mocker.patch(
        "app.domains.controller.DomainService.list_domains",
        new_callable=AsyncMock,
        return_value=mock_domains,
    )

    response = await client.get("/api/v1/domains/")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 2
    assert data["data"][0]["name"] == "ui"
    assert data["data"][1]["name"] == "marketing"


@pytest.mark.asyncio
async def test_get_domain_by_name(client: AsyncClient, mocker):
    mock_domain = Domain(
        uuid="uuid-1",
        name="ui",
        description="UI domain",
        content_types=["button"],
        rules={"creativity": "low"},
    )
    mocker.patch(
        "app.domains.controller.DomainService.get_by_name",
        new_callable=AsyncMock,
        return_value=mock_domain,
    )

    response = await client.get("/api/v1/domains/ui")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "ui"


@pytest.mark.asyncio
async def test_get_domain_not_found(client: AsyncClient, mocker):
    mocker.patch(
        "app.domains.controller.DomainService.get_by_name",
        new_callable=AsyncMock,
        return_value=None,
    )

    response = await client.get("/api/v1/domains/non-existent")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "Domain not found"


@pytest.mark.asyncio
async def test_update_domain(client: AsyncClient, mocker):
    mock_domain = Domain(
        uuid="uuid-1",
        name="ui",
        description="Updated UI domain",
        content_types=["button"],
        rules={"creativity": "very_low"},
    )
    mocker.patch(
        "app.domains.controller.DomainService.update",
        new_callable=AsyncMock,
        return_value=mock_domain,
    )

    response = await client.put(
        "/api/v1/domains/ui",
        json={
            "description": "Updated UI domain",
            "rules": {"creativity": "very_low"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["description"] == "Updated UI domain"
    assert data["data"]["rules"]["creativity"] == "very_low"


@pytest.mark.asyncio
async def test_delete_domain(client: AsyncClient, mocker):
    mocker.patch(
        "app.domains.controller.DomainService.delete",
        new_callable=AsyncMock,
        return_value=True,
    )

    response = await client.delete("/api/v1/domains/ui")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"] is None
