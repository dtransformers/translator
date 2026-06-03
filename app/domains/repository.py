from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.domains.models import Domain
from app.domains.schemas import DomainCreate

class DomainRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, db_domain: Domain) -> Domain:
        self.session.add(db_domain)
        await self.session.commit()
        await self.session.refresh(db_domain)
        return db_domain

    async def get_by_name(self, name: str) -> Domain | None:
        stmt = select(Domain).where(Domain.name == name)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_domains(self) -> list[Domain]:
        stmt = select(Domain)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save(self, db_domain: Domain) -> Domain:
        await self.session.commit()
        await self.session.refresh(db_domain)
        return db_domain

    async def delete(self, db_domain: Domain) -> None:
        await self.session.delete(db_domain)
        await self.session.commit()
