"""
Brands API endpoints (v1).

Full CRUD for Brand entities used to inject context into translations.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.core.auth import require_auth
from app.brands.service import BrandService
from app.brands.schemas import BrandCreate, BrandUpdate, BrandResponse
from app.schemas.translation import ApiResponse
from app.schemas.errors import CRUD_ERRORS, COMMON_ERRORS

router = APIRouter(dependencies=[Depends(require_auth)])


@router.post(
    "",
    response_model=ApiResponse[BrandResponse],
    summary="Create a brand",
    description=(
        "Register a new brand profile. Brand profiles inject domain-specific "
        "context (industry, tone, audience, keywords, glossary) into the LLM "
        "translation pipeline for higher-quality, brand-aligned translations."
    ),
    response_description="The newly created brand",
    operation_id="create_brand",
    status_code=201,
    responses=COMMON_ERRORS,
)
async def create_brand(
    brand_in: BrandCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new brand profile."""
    svc = BrandService(db)
    brand = await svc.create(brand_in)
    return ApiResponse(
        success=True,
        data=BrandResponse.model_validate(brand),
        error=None,
    )


@router.get(
    "",
    response_model=ApiResponse[List[BrandResponse]],
    summary="List all brands",
    description="Retrieve a list of all registered brand profiles.",
    response_description="Array of brand profiles",
    operation_id="list_brands",
    responses=COMMON_ERRORS,
)
async def get_all_brands(db: AsyncSession = Depends(get_db)):
    """List every registered brand."""
    svc = BrandService(db)
    brands = await svc.get_all()
    return ApiResponse(
        success=True,
        data=[BrandResponse.model_validate(b) for b in brands],
        error=None,
    )


@router.get(
    "/{brand_uuid}",
    response_model=ApiResponse[BrandResponse],
    summary="Get a brand by UUID",
    description="Retrieve a single brand profile by its unique identifier.",
    response_description="The requested brand profile",
    operation_id="get_brand",
    responses=CRUD_ERRORS,
)
async def get_brand(
    brand_uuid: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a brand by UUID."""
    svc = BrandService(db)
    brand = await svc.get_by_uuid(brand_uuid)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return ApiResponse(
        success=True,
        data=BrandResponse.model_validate(brand),
        error=None,
    )


@router.put(
    "/{brand_uuid}",
    response_model=ApiResponse[BrandResponse],
    summary="Update a brand",
    description=(
        "Update an existing brand profile. Only the fields provided in the "
        "request body will be modified; omitted fields remain unchanged."
    ),
    response_description="The updated brand profile",
    operation_id="update_brand",
    responses=CRUD_ERRORS,
)
async def update_brand(
    brand_uuid: str,
    brand_in: BrandUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a brand by UUID."""
    svc = BrandService(db)
    updated = await svc.update(brand_uuid, brand_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Brand not found")
    return ApiResponse(
        success=True,
        data=BrandResponse.model_validate(updated),
        error=None,
    )


@router.delete(
    "/{brand_uuid}",
    response_model=ApiResponse[None],
    summary="Delete a brand",
    description="Permanently delete a brand profile by its UUID.",
    response_description="Confirmation of deletion",
    operation_id="delete_brand",
    responses=CRUD_ERRORS,
)
async def delete_brand(
    brand_uuid: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a brand by UUID."""
    svc = BrandService(db)
    deleted = await svc.delete(brand_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Brand not found")
    return ApiResponse(success=True, data=None, error=None)
