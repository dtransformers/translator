from sqlalchemy.ext.asyncio import AsyncSession
from app.brands.service import BrandService
from app.brands.schemas import BrandCreate, BrandUpdate
from app.brands.models import Brand

class BrandController:
    def __init__(self, db: AsyncSession):
        self.service = BrandService(db)

    async def create(self, brand_in: BrandCreate) -> Brand:
        return await self.service.create(brand_in)

    async def get_all(self) -> list[Brand]:
        return await self.service.get_all()

    async def get_by_uuid(self, brand_uuid: str) -> Brand | None:
        return await self.service.get_by_uuid(brand_uuid)

    async def update(self, brand_uuid: str, brand_in: BrandUpdate) -> Brand | None:
        return await self.service.update(brand_uuid, brand_in)

    async def delete(self, brand_uuid: str) -> bool:
        return await self.service.delete(brand_uuid)
