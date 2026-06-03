import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.models import Domain
from app.domains.schemas import DomainCreate, DomainUpdate
from app.domains.repository import DomainRepository

logger = logging.getLogger(__name__)

class DomainService:
    def __init__(self, db: AsyncSession):
        self._repo = DomainRepository(db)

    async def create(self, domain_in: DomainCreate) -> Domain:
        logger.info(f"Creating domain: {domain_in.name}")
        db_domain = Domain(
            name=domain_in.name,
            description=domain_in.description,
            content_types=domain_in.content_types,
            rules=domain_in.rules.model_dump(exclude_unset=True)
        )
        return await self._repo.create(db_domain)

    async def get_by_name(self, name: str) -> Domain | None:
        return await self._repo.get_by_name(name)

    async def list_domains(self) -> list[Domain]:
        return await self._repo.list_domains()

    async def update(self, name: str, domain_in: DomainUpdate) -> Domain | None:
        db_domain = await self._repo.get_by_name(name)
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
            
        return await self._repo.save(db_domain)

    async def delete(self, name: str) -> bool:
        db_domain = await self._repo.get_by_name(name)
        if not db_domain:
            return False
        
        await self._repo.delete(db_domain)
        return True
