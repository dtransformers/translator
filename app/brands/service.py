"""
BrandService — the single public interface for all Brand entity operations.

External modules (controllers, endpoints) must use this service.
Never import BrandRepository directly outside this module.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.brands.models import Brand
from app.brands.repository import BrandRepository
from app.brands.schemas import BrandCreate, BrandUpdate

logger = logging.getLogger(__name__)


class BrandService:
    """
    Service layer for the Brand entity.

    Encapsulates all CRUD and brand-context operations.
    The repository is internal — only this service may call it.
    """

    def __init__(self, db: AsyncSession):
        self._repo = BrandRepository(db)
        self._db = db

    # ------------------------------------------------------------------ #
    #  CRUD
    # ------------------------------------------------------------------ #

    async def create(self, brand_in: BrandCreate) -> Brand:
        """Create a new brand."""
        return await self._repo.create(brand_in)

    async def get_by_uuid(self, brand_uuid: str) -> Brand | None:
        """Fetch a single brand by its UUID."""
        return await self._repo.get_by_uuid(brand_uuid)

    async def get_all(self) -> list[Brand]:
        """Fetch all brands."""
        return await self._repo.get_all()

    async def update(self, brand_uuid: str, brand_in: BrandUpdate) -> Brand | None:
        """
        Update a brand identified by UUID.
        Returns the updated Brand, or None if not found.
        """
        brand = await self._repo.get_by_uuid(brand_uuid)
        if not brand:
            return None
        return await self._repo.update(brand, brand_in)

    async def delete(self, brand_uuid: str) -> bool:
        """
        Delete a brand identified by UUID.
        Returns True if deleted, False if not found.
        """
        brand = await self._repo.get_by_uuid(brand_uuid)
        if not brand:
            return False
        await self._repo.delete(brand)
        return True

    # ------------------------------------------------------------------ #
    #  Brand Context (used by translation pipeline)
    # ------------------------------------------------------------------ #

    async def get_brand_context(self, brand_uuid: str | None = None) -> dict[str, Any]:
        """
        Build the brand context dict for translation prompts.

        If a brand_uuid is provided and found, its fields override the defaults.
        Otherwise returns generic default context values.
        """
        context: dict[str, Any] = {
            "industry": "General Technology",
            "tone": "Professional, clear, and objective",
            "audience": "General audience, globally",
            "keywords": [],
            "entities": [],
            "summary": "General translation of user provided text.",
            "glossary": {},
        }

        if brand_uuid:
            brand = await self._repo.get_by_uuid(brand_uuid)
            if brand:
                context.update({
                    "industry": brand.industry or context["industry"],
                    "tone": brand.tone or context["tone"],
                    "audience": brand.audience or context["audience"],
                    "keywords": brand.keywords or context["keywords"],
                    "entities": brand.entities or context["entities"],
                    "summary": brand.summary or context["summary"],
                })

        return context
