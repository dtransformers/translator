from sqlalchemy import Column, Integer, Text, String, DateTime
from sqlalchemy.sql import func
from app.db.base import Base

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
    etag = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)
    total_chars = Column(Integer, nullable=True)
    status = Column(String(50), default="PENDING") 
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
