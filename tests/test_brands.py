import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from app.brands.models import Brand


@pytest.mark.asyncio
async def test_create_brand(client: AsyncClient, mocker):
    mock_brand = Brand(id=1, uuid="test-uuid-123", name="TestBrand", industry="Tech", keywords=[], entities=[])
    mocker.patch(
        "app.brands.router.BrandController.create",
        new_callable=AsyncMock,
        return_value=mock_brand,
    )

    response = await client.post("/api/v1/brands", json={
        "name": "TestBrand",
        "industry": "Tech"
    })

    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "TestBrand"
    assert data["data"]["uuid"] == "test-uuid-123"


@pytest.mark.asyncio
async def test_get_brand(client: AsyncClient, mocker):
    mock_brand = Brand(id=1, uuid="test-uuid-123", name="TestBrand", industry="Tech", keywords=[], entities=[])
    mocker.patch(
        "app.brands.router.BrandController.get_by_uuid",
        new_callable=AsyncMock,
        return_value=mock_brand,
    )

    response = await client.get("/api/v1/brands/test-uuid-123")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "TestBrand"


@pytest.mark.asyncio
async def test_get_brand_not_found(client: AsyncClient, mocker):
    mocker.patch(
        "app.brands.router.BrandController.get_by_uuid",
        new_callable=AsyncMock,
        return_value=None,
    )

    response = await client.get("/api/v1/brands/non-existent-uuid")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "Brand not found"


# --------------------------------------------------------------------------- #
#  BrandService.get_brand_context (issue #12)
# --------------------------------------------------------------------------- #

from unittest.mock import MagicMock

from app.brands.service import BrandService


def _db_returning(brand):
    """Fake AsyncSession whose execute() yields `brand` from scalars().first()."""
    result = MagicMock()
    result.scalars.return_value.first.return_value = brand
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_get_brand_context_with_existing_brand():
    brand = Brand(
        uuid="brand-1", name="Acme", industry="Retail", tone="Playful",
        audience=None, keywords=["deals"], entities=[], summary=None,
    )
    svc = BrandService(_db_returning(brand))

    context = await svc.get_brand_context("brand-1")

    assert context["name"] == "Acme"
    assert context["industry"] == "Retail"
    assert context["tone"] == "Playful"
    assert context["keywords"] == ["deals"]
    # Missing fields fall back to defaults
    assert context["audience"] == "General audience, globally"
    assert context["summary"] == "General translation of user provided text."


@pytest.mark.asyncio
async def test_get_brand_context_with_unknown_brand_returns_defaults():
    svc = BrandService(_db_returning(None))

    context = await svc.get_brand_context("missing")

    assert "name" not in context
    assert context["industry"] == "General Technology"


@pytest.mark.asyncio
async def test_get_brand_context_without_uuid_skips_db():
    db = _db_returning(None)
    svc = BrandService(db)

    context = await svc.get_brand_context(None)

    db.execute.assert_not_called()
    assert context["tone"] == "Professional, clear, and objective"
