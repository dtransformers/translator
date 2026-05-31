from sqlalchemy import Column, Integer, Boolean, Float, DateTime, Text, String
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
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

    # Caching Fields
    text_hash = Column(String(64), nullable=True, index=True)
    normalized_text = Column(Text, nullable=True)
    normalized_hash = Column(String(64), nullable=True, index=True)
    embedding = Column(Vector(384), nullable=True) # Assuming all-MiniLM-L6-v2 which has 384 dims
    segment_type = Column(String(50), nullable=True) # e.g. "Sentence Unit", "Atomic Element", "Structured Template"

class ReusableUnit(Base):
    __tablename__ = "reusable_units"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_text = Column(Text, nullable=False)
    target_language = Column(Text, nullable=False)
    translation = Column(Text, nullable=False)
    unit_type = Column(String(50), nullable=False) # e.g. "entity", "phrase"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class BucketTranslationOperation(Base):
    __tablename__ = "bucket_translation_operations"

    id = Column(String(36), primary_key=True)
    bucket_name = Column(String(255), nullable=False)
    source_prefix = Column(String(1024), nullable=False)
    target_prefix = Column(String(1024), nullable=False)
    source_lang = Column(String(10), nullable=False)
    target_lang = Column(String(10), nullable=False)
    status = Column(String(50), default="PENDING") 
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    failed_files = Column(Integer, default=0)
    skipped_files = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class FileTranslationOperation(Base):
    __tablename__ = "file_translation_operations"

    id = Column(String(36), primary_key=True)
    bucket_operation_id = Column(String(36), nullable=False, index=True)
    file_key = Column(String(1024), nullable=False)
    file_name = Column(String(255), nullable=True)
    extension = Column(String(50), nullable=True)
    tag = Column(String(255), nullable=True)
    file_hash = Column(String(255), nullable=True, index=True)
    file_size = Column(Integer, nullable=True)
    total_chars = Column(Integer, nullable=True)
    status = Column(String(50), default="PENDING") 
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
