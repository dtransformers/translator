"""
BrandService — the single public interface for all Brand entity operations.

External modules (controllers, endpoints) must use this service.
Never import BrandRepository directly outside this module.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.brands.models import Brand
from app.brands.schemas import BrandCreate, BrandUpdate

logger = logging.getLogger(__name__)


class BrandService:
    """
    Service layer for the Brand entity.

    Encapsulates all CRUD and brand-context operations.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    # ------------------------------------------------------------------ #
    #  CRUD
    # ------------------------------------------------------------------ #

    async def create(self, brand_in: BrandCreate) -> Brand:
        """Create a new brand."""
        db_brand = Brand(**brand_in.model_dump())
        self._db.add(db_brand)
        await self._db.commit()
        await self._db.refresh(db_brand)
        return db_brand

    async def get_by_uuid(self, brand_uuid: str) -> Brand | None:
        """Fetch a single brand by its UUID."""
        result = await self._db.execute(select(Brand).filter(Brand.uuid == brand_uuid))
        return result.scalars().first()

    async def get_all(self) -> list[Brand]:
        """Fetch all brands."""
        result = await self._db.execute(select(Brand))
        return list(result.scalars().all())

    async def update(self, brand_uuid: str, brand_in: BrandUpdate) -> Brand | None:
        """
        Update a brand identified by UUID.
        Returns the updated Brand, or None if not found.
        """
        brand = await self.get_by_uuid(brand_uuid)
        if not brand:
            return None
        update_data = brand_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(brand, field, value)
        await self._db.commit()
        await self._db.refresh(brand)
        return brand

    async def delete(self, brand_uuid: str) -> bool:
        """
        Delete a brand identified by UUID.
        Returns True if deleted, False if not found.
        """
        brand = await self.get_by_uuid(brand_uuid)
        if not brand:
            return False
        await self._db.delete(brand)
        await self._db.commit()
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
                    "name": brand.name,
                    "industry": brand.industry or context["industry"],
                    "tone": brand.tone or context["tone"],
                    "audience": brand.audience or context["audience"],
                    "keywords": brand.keywords or context["keywords"],
                    "entities": brand.entities or context["entities"],
                    "summary": brand.summary or context["summary"],
                })

        return context
