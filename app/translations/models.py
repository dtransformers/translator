from sqlalchemy import Column, Integer, Boolean, Float, DateTime, Text
from sqlalchemy.sql import func
from app.db.base import Base

class Translation(Base):
    __tablename__ = "translations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(Text, nullable=True)
    property = Column(Text, nullable=True)
    value = Column(Text, nullable=False)
    language = Column(Text, nullable=False)
    translation = Column(Text, nullable=True)
    translation_language = Column(Text, nullable=True)
    detected_input_lang = Column(Text, nullable=True)
    detected_output_lang = Column(Text, nullable=True)
    is_successed = Column(Boolean, default=False)
    score = Column(Float, default=None, nullable=True)
    is_approved = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime(timezone=True), default=None, nullable=True)
    notes = Column(Text, default=None, nullable=True)
    translation_time = Column(Float, default=None, nullable=True)
    input_size = Column(Integer, default=None, nullable=True)
    output_size = Column(Integer, default=None, nullable=True)
    size_difference = Column(Float, default=None, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
