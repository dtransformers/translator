from fastapi import APIRouter

from app.brands.router import router as brands_router
from app.domains.router import router as domains_router
from app.text_translation.router import (
    translation_router,
    review_router,
    debug_router,
)
from app.document_translation.router import router as document_router
from app.bucket_translation.router import router as bucket_router

api_router = APIRouter()

api_router.include_router(translation_router, tags=["translation"])
api_router.include_router(document_router, tags=["documents"])
api_router.include_router(bucket_router, tags=["buckets"])
api_router.include_router(brands_router, prefix="/brands", tags=["brands"])
api_router.include_router(domains_router)
api_router.include_router(review_router)
api_router.include_router(debug_router)
