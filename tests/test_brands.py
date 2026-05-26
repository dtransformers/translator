import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from app.brands.models import Brand

@pytest.mark.asyncio
async def test_create_brand(client: AsyncClient, mocker):
    mock_brand = Brand(id=1, uuid="test-uuid-123", name="TestBrand", industry="Tech")
    mocker.patch("app.api.v1.endpoints.brands.BrandRepository.create", new_callable=AsyncMock, return_value=mock_brand)
    
    response = await client.post("/api/v1/brands/brands", json={
        "name": "TestBrand",
        "industry": "Tech"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "TestBrand"
    assert data["data"]["uuid"] == "test-uuid-123"

@pytest.mark.asyncio
async def test_get_brand(client: AsyncClient, mocker):
    mock_brand = Brand(id=1, uuid="test-uuid-123", name="TestBrand", industry="Tech")
    mocker.patch("app.api.v1.endpoints.brands.BrandRepository.get_by_uuid", new_callable=AsyncMock, return_value=mock_brand)
    
    response = await client.get("/api/v1/brands/brands/test-uuid-123")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "TestBrand"

@pytest.mark.asyncio
async def test_get_brand_not_found(client: AsyncClient, mocker):
    mocker.patch("app.api.v1.endpoints.brands.BrandRepository.get_by_uuid", new_callable=AsyncMock, return_value=None)
    
    response = await client.get("/api/v1/brands/brands/non-existent-uuid")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "Brand not found"
