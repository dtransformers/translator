from sqlalchemy import Column, String, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base

class Domain(Base):
    __tablename__ = "domains"

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(String(500), nullable=True)
    content_types = Column(JSON, nullable=True)
    rules = Column(JSON, nullable=False)
