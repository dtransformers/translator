from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.translations.models import Translation


async def get_translation_cache(
    text: str,
    source_lang: str,
    target_lang: str,
    db: AsyncSession
) -> Translation | None:

    result = await db.execute(
        select(Translation).where(
            Translation.value == text,
            Translation.language == source_lang,
            Translation.translation_language == target_lang,
            Translation.is_successed == True
        )
    )
    return result.scalar_one_or_none()
