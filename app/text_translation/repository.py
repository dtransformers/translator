from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.text_translation.models import Translation, ReusableUnit

class TranslationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Translation:
        new_translation = Translation(**kwargs)
        self.session.add(new_translation)
        await self.session.commit()
        await self.session.refresh(new_translation)
        return new_translation

    async def get_by_id(self, translation_id: int) -> Translation | None:
        result = await self.session.execute(select(Translation).where(Translation.id == translation_id))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Translation]:
        result = await self.session.execute(select(Translation).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def update(self, translation_id: int, **kwargs) -> Translation | None:
        translation = await self.get_by_id(translation_id)
        if not translation:
            return None
        
        for key, value in kwargs.items():
            setattr(translation, key, value)
            
        await self.session.commit()
        await self.session.refresh(translation)
        return translation

    async def execute_query(self, query) -> Any:
        # Generic executor for specific pipeline queries
        return await self.session.execute(query)


class ReusableUnitRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, source_text: str, target_language: str, translation: str, unit_type: str) -> ReusableUnit:
        unit = ReusableUnit(
            source_text=source_text,
            target_language=target_language,
            translation=translation,
            unit_type=unit_type
        )
        self.session.add(unit)
        await self.session.commit()
        await self.session.refresh(unit)
        return unit

    async def list_by_target_language(self, target_language: str | None = None) -> list[ReusableUnit]:
        query = select(ReusableUnit)
        if target_language:
            query = query.where(ReusableUnit.target_language == target_language)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, unit_id: int) -> ReusableUnit | None:
        result = await self.session.execute(select(ReusableUnit).where(ReusableUnit.id == unit_id))
        return result.scalars().first()

    async def delete(self, unit: ReusableUnit) -> None:
        await self.session.delete(unit)
        await self.session.commit()
