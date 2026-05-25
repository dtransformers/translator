from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
import uuid
from app.db.base import Base

class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    website = Column(String, nullable=True)
    name = Column(String, nullable=False, unique=True)
    industry = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    keywords = Column(ARRAY(String), default=list)
    audience = Column(String, nullable=True)
    entities = Column(ARRAY(String), default=list)
    tone = Column(String, nullable=True)
