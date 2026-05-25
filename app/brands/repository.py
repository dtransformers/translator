from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .models import Brand
from .schemas import BrandCreate, BrandUpdate

class BrandRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, brand_in: BrandCreate) -> Brand:
        db_brand = Brand(**brand_in.model_dump())
        self.session.add(db_brand)
        await self.session.commit()
        await self.session.refresh(db_brand)
        return db_brand

    async def get_by_uuid(self, brand_uuid: str) -> Brand | None:
        result = await self.session.execute(select(Brand).filter(Brand.uuid == brand_uuid))
        return result.scalars().first()

    async def get_all(self) -> list[Brand]:
        result = await self.session.execute(select(Brand))
        return list(result.scalars().all())

    async def update(self, db_brand: Brand, brand_in: BrandUpdate) -> Brand:
        update_data = brand_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_brand, field, value)
        await self.session.commit()
        await self.session.refresh(db_brand)
        return db_brand

    async def delete(self, db_brand: Brand) -> None:
        await self.session.delete(db_brand)
        await self.session.commit()
