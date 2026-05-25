from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .models import Translation

class TranslationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_translation(self, **kwargs) -> Translation:
        new_translation = Translation(**kwargs)
        self.session.add(new_translation)
        await self.session.commit()
        await self.session.refresh(new_translation)
        return new_translation

    async def get_translation_by_id(self, translation_id: int) -> Translation | None:
        result = await self.session.execute(select(Translation).where(Translation.id == translation_id))
        return result.scalar_one_or_none()

    async def get_all_translations(self, skip: int = 0, limit: int = 100) -> list[Translation]:
        result = await self.session.execute(select(Translation).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def update_translation(self, translation_id: int, **kwargs) -> Translation | None:
        translation = await self.get_translation_by_id(translation_id)
        if not translation:
            return None
        
        for key, value in kwargs.items():
            setattr(translation, key, value)
            
        await self.session.commit()
        await self.session.refresh(translation)
        return translation
