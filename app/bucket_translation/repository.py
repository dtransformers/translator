from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from app.bucket_translation.models import BucketTranslationOperation, FileTranslationOperation

class BucketTranslationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_operation(self, operation: BucketTranslationOperation) -> BucketTranslationOperation:
        self.session.add(operation)
        await self.session.commit()
        await self.session.refresh(operation)
        return operation

    async def get_operation(self, operation_id: str) -> BucketTranslationOperation | None:
        result = await self.session.execute(
            select(BucketTranslationOperation).where(BucketTranslationOperation.id == operation_id)
        )
        return result.scalars().first()

    async def update_operation(self, operation_id: str, **kwargs) -> None:
        await self.session.execute(
            update(BucketTranslationOperation)
            .where(BucketTranslationOperation.id == operation_id)
            .values(**kwargs)
        )
        await self.session.commit()

    async def increment_operation_counter(self, operation_id: str, field_name: str, value: int = 1) -> None:
        # Increment counters dynamically
        op = await self.get_operation(operation_id)
        if op:
            current_val = getattr(op, field_name) or 0
            setattr(op, field_name, current_val + value)
            await self.session.commit()

    async def create_file_operation(self, file_op: FileTranslationOperation) -> FileTranslationOperation:
        self.session.add(file_op)
        await self.session.commit()
        await self.session.refresh(file_op)
        return file_op

    async def get_file_operations_by_operation_id(self, operation_id: str) -> list[FileTranslationOperation]:
        result = await self.session.execute(
            select(FileTranslationOperation).where(FileTranslationOperation.bucket_operation_id == operation_id)
        )
        return list(result.scalars().all())

    async def update_file_operation(self, file_id: str, **kwargs) -> None:
        await self.session.execute(
            update(FileTranslationOperation)
            .where(FileTranslationOperation.id == file_id)
            .values(**kwargs)
        )
        await self.session.commit()

    async def find_cached_successful_file_operation(
        self, source_key: str, file_hash: str, target_lang: str
    ) -> Any:
        stmt = select(FileTranslationOperation, BucketTranslationOperation).join(
            BucketTranslationOperation,
            FileTranslationOperation.bucket_operation_id == BucketTranslationOperation.id
        ).where(
            FileTranslationOperation.file_key == source_key,
            FileTranslationOperation.file_hash == file_hash,
            FileTranslationOperation.status == "SUCCESS",
            BucketTranslationOperation.target_lang == target_lang
        )
        result = await self.session.execute(stmt)
        return result.first()
