from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.brands.repository import BrandRepository

async def get_brand_context(db: AsyncSession, brand_uuid: str | None = None) -> Dict[str, Any]:
    """
    Fetches the brand context from the database if a UUID is provided.
    Otherwise, returns an abstract generic context.
    """
    context = {
        "industry": "General Technology",
        "tone": "Professional, clear, and objective",
        "audience": "General audience, globally",
        "keywords": [],
        "entities": [],
        "summary": "General translation of user provided text.",
        "glossary": {}
    }

    if brand_uuid:
        repo = BrandRepository(db)
        brand = await repo.get_by_uuid(brand_uuid)
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
