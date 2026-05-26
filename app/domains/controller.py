from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.domains.schemas import DomainCreate, DomainUpdate, DomainResponse
from app.domains.service import DomainService
from app.core.auth import require_auth
from app.schemas.translation import ApiResponse

router = APIRouter(
    prefix="/domains",
    tags=["domains"],
    dependencies=[Depends(require_auth)]
)

@router.post("/", response_model=ApiResponse[DomainResponse], status_code=status.HTTP_201_CREATED)
async def create_domain(domain_in: DomainCreate, db: AsyncSession = Depends(get_db)):
    service = DomainService(db)
    existing = await service.get_by_name(domain_in.name)
    if existing:
        raise HTTPException(status_code=400, detail="Domain with this name already exists")
    
    domain = await service.create(domain_in)
    return ApiResponse(
        success=True,
        data=DomainResponse.model_validate(domain),
        error=None
    )

@router.get("/", response_model=ApiResponse[List[DomainResponse]])
async def list_domains(db: AsyncSession = Depends(get_db)):
    service = DomainService(db)
    domains = await service.list_domains()
    return ApiResponse(
        success=True,
        data=[DomainResponse.model_validate(d) for d in domains],
        error=None
    )

@router.get("/{name}", response_model=ApiResponse[DomainResponse])
async def get_domain(name: str, db: AsyncSession = Depends(get_db)):
    service = DomainService(db)
    domain = await service.get_by_name(name)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return ApiResponse(
        success=True,
        data=DomainResponse.model_validate(domain),
        error=None
    )

@router.put("/{name}", response_model=ApiResponse[DomainResponse])
async def update_domain(name: str, domain_in: DomainUpdate, db: AsyncSession = Depends(get_db)):
    service = DomainService(db)
    domain = await service.update(name, domain_in)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return ApiResponse(
        success=True,
        data=DomainResponse.model_validate(domain),
        error=None
    )

@router.delete("/{name}", response_model=ApiResponse[None])
async def delete_domain(name: str, db: AsyncSession = Depends(get_db)):
    service = DomainService(db)
    success = await service.delete(name)
    if not success:
        raise HTTPException(status_code=404, detail="Domain not found")
    return ApiResponse(
        success=True,
        data=None,
        error=None
    )

