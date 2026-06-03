from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.service import DomainService
from app.domains.schemas import DomainCreate, DomainUpdate
from app.domains.models import Domain

class DomainController:
    def __init__(self, db: AsyncSession):
        self.service = DomainService(db)

    async def create(self, domain_in: DomainCreate) -> Domain:
        return await self.service.create(domain_in)

    async def get_by_name(self, name: str) -> Domain | None:
        return await self.service.get_by_name(name)

    async def list_domains(self) -> list[Domain]:
        return await self.service.list_domains()

    async def update(self, name: str, domain_in: DomainUpdate) -> Domain | None:
        return await self.service.update(name, domain_in)

    async def delete(self, name: str) -> bool:
        return await self.service.delete(name)
