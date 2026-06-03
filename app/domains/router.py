from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Annotated

from app.db.session import get_db
from app.domains.schemas import DomainCreate, DomainUpdate, DomainResponse
from app.domains.controller import DomainController
from app.core.auth import require_auth
from app.schemas.base import ApiResponse
from app.schemas.errors import CRUD_ERRORS, COMMON_ERRORS

router = APIRouter(
    prefix="/domains",
    tags=["domains"],
    dependencies=[Depends(require_auth)]
)

DOMAIN_NOT_FOUND_DETAIL = "Domain not found"

@router.post("/", response_model=ApiResponse[DomainResponse], status_code=status.HTTP_201_CREATED, responses=COMMON_ERRORS)
async def create_domain(domain_in: DomainCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    ctl = DomainController(db)
    existing = await ctl.get_by_name(domain_in.name)
    if existing:
        raise HTTPException(status_code=400, detail="Domain with this name already exists")
    
    domain = await ctl.create(domain_in)
    return ApiResponse(
        success=True,
        data=DomainResponse.model_validate(domain),
        error=None
    )

@router.get("/", response_model=ApiResponse[List[DomainResponse]])
async def list_domains(db: Annotated[AsyncSession, Depends(get_db)]):
    ctl = DomainController(db)
    domains = await ctl.list_domains()
    return ApiResponse(
        success=True,
        data=[DomainResponse.model_validate(d) for d in domains],
        error=None
    )

@router.get("/{name}", response_model=ApiResponse[DomainResponse], responses=CRUD_ERRORS)
async def get_domain(name: str, db: Annotated[AsyncSession, Depends(get_db)]):
    ctl = DomainController(db)
    domain = await ctl.get_by_name(name)
    if not domain:
        raise HTTPException(status_code=404, detail=DOMAIN_NOT_FOUND_DETAIL)
    return ApiResponse(
        success=True,
        data=DomainResponse.model_validate(domain),
        error=None
    )

@router.put("/{name}", response_model=ApiResponse[DomainResponse], responses=CRUD_ERRORS)
async def update_domain(name: str, domain_in: DomainUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    ctl = DomainController(db)
    domain = await ctl.update(name, domain_in)
    if not domain:
        raise HTTPException(status_code=404, detail=DOMAIN_NOT_FOUND_DETAIL)
    return ApiResponse(
        success=True,
        data=DomainResponse.model_validate(domain),
        error=None
    )

@router.delete("/{name}", response_model=ApiResponse[None], responses=CRUD_ERRORS)
async def delete_domain(name: str, db: Annotated[AsyncSession, Depends(get_db)]):
    ctl = DomainController(db)
    success = await ctl.delete(name)
    if not success:
        raise HTTPException(status_code=404, detail=DOMAIN_NOT_FOUND_DETAIL)
    return ApiResponse(
        success=True,
        data=None,
        error=None
    )
