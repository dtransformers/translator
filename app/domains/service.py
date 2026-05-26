import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.domains.models import Domain
from app.domains.schemas import DomainCreate, DomainUpdate

logger = logging.getLogger(__name__)

class DomainService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, domain_in: DomainCreate) -> Domain:
        logger.info(f"Creating domain: {domain_in.name}")
        db_domain = Domain(
            name=domain_in.name,
            description=domain_in.description,
            content_types=domain_in.content_types,
            rules=domain_in.rules.model_dump(exclude_unset=True)
        )
        self.db.add(db_domain)
        await self.db.commit()
        await self.db.refresh(db_domain)
        return db_domain

    async def get_by_name(self, name: str) -> Domain | None:
        stmt = select(Domain).where(Domain.name == name)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_domains(self) -> list[Domain]:
        stmt = select(Domain)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, name: str, domain_in: DomainUpdate) -> Domain | None:
        db_domain = await self.get_by_name(name)
        if not db_domain:
            return None
        
        update_data = domain_in.model_dump(exclude_unset=True)
        
        if "rules" in update_data:
            current_rules = db_domain.rules or {}
            current_rules.update(update_data["rules"])
            db_domain.rules = current_rules
            del update_data["rules"]
            
        for field, value in update_data.items():
            setattr(db_domain, field, value)
            
        await self.db.commit()
        await self.db.refresh(db_domain)
        return db_domain

    async def delete(self, name: str) -> bool:
        db_domain = await self.get_by_name(name)
        if not db_domain:
            return False
        
        await self.db.delete(db_domain)
        await self.db.commit()
        return True

