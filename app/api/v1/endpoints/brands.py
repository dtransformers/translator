from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.brands.schemas import BrandCreate, BrandUpdate, BrandResponse
from app.brands.repository import BrandRepository
from app.schemas.translation import ApiResponse

router = APIRouter()

@router.post("/brands", response_model=ApiResponse[BrandResponse])
async def create_brand(
    brand_in: BrandCreate,
    db: AsyncSession = Depends(get_db)
):
    repo = BrandRepository(db)
    brand = await repo.create(brand_in)
    return ApiResponse(
        success=True,
        data=BrandResponse.model_validate(brand),
        error=None
    )

@router.get("/brands", response_model=ApiResponse[List[BrandResponse]])
async def get_all_brands(
    db: AsyncSession = Depends(get_db)
):
    repo = BrandRepository(db)
    brands = await repo.get_all()
    return ApiResponse(
        success=True,
        data=[BrandResponse.model_validate(b) for b in brands],
        error=None
    )

@router.get("/brands/{brand_uuid}", response_model=ApiResponse[BrandResponse])
async def get_brand(
    brand_uuid: str,
    db: AsyncSession = Depends(get_db)
):
    repo = BrandRepository(db)
    brand = await repo.get_by_uuid(brand_uuid)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    return ApiResponse(
        success=True,
        data=BrandResponse.model_validate(brand),
        error=None
    )

@router.put("/brands/{brand_uuid}", response_model=ApiResponse[BrandResponse])
async def update_brand(
    brand_uuid: str,
    brand_in: BrandUpdate,
    db: AsyncSession = Depends(get_db)
):
    repo = BrandRepository(db)
    brand = await repo.get_by_uuid(brand_uuid)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
        
    updated_brand = await repo.update(brand, brand_in)
    return ApiResponse(
        success=True,
        data=BrandResponse.model_validate(updated_brand),
        error=None
    )

@router.delete("/brands/{brand_uuid}", response_model=ApiResponse[None])
async def delete_brand(
    brand_uuid: str,
    db: AsyncSession = Depends(get_db)
):
    repo = BrandRepository(db)
    brand = await repo.get_by_uuid(brand_uuid)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
        
    await repo.delete(brand)
    return ApiResponse(
        success=True,
        data=None,
        error=None
    )
