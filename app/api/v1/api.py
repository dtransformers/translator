from fastapi import APIRouter

from app.api.v1.endpoints import translation, brands, domains, review, debug

api_router = APIRouter()

# API versioning setup: all v1 endpoints are included here
api_router.include_router(translation.router, tags=["translation"])
api_router.include_router(brands.router, prefix="/brands", tags=["brands"])
api_router.include_router(domains.router)
api_router.include_router(review.router, prefix="/review", tags=["review"])
api_router.include_router(debug.router, prefix="/debug", tags=["debug"])
