from pydantic import BaseModel, Field
from typing import Optional, Any

class BucketTranslationRequest(BaseModel):
    bucket_name: str = Field(..., description="The name of the S3/MinIO bucket")
    source_prefix: str = Field(..., description="The prefix of the files to translate (e.g. 'assets/content/en/')")
    target_prefix: str = Field(..., description="The prefix to upload translated files (e.g. 'assets/content/ar/')")
    source_lang: str = Field(..., description="The source language code")
    target_lang: str = Field(..., description="The target language code")
    brand_uuid: Optional[str] = Field(None, description="Optional brand UUID for tone and glossary context")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "bucket_name": "my-bucket",
                    "source_prefix": "content/en/",
                    "target_prefix": "content/ar/",
                    "source_lang": "en",
                    "target_lang": "ar",
                    "brand_uuid": "123e4567-e89b-12d3-a456-426614174000"
                }
            ]
        }
    }


class BucketTranslationData(BaseModel):
    message: str = Field(..., description="Status message of the bucket translation process")
    processed_files: int = Field(0, description="Number of files processed")
    failed_files: int = Field(0, description="Number of files failed")
    details: list[dict] = Field([], description="Details of each file processed")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Bucket translation completed successfully",
                    "processed_files": 5,
                    "failed_files": 0,
                    "details": [{"file": "content/en/about.json", "status": "success", "target_key": "content/ar/about.json"}]
                }
            ]
        }
    }


class FileOperationStatusResponse(BaseModel):
    id: str
    file_key: str
    file_name: Optional[str] = None
    extension: Optional[str] = None
    tag: Optional[str] = None
    status: str
    file_size: Optional[int] = None
    etag: Optional[str] = None
    total_chars: Optional[int] = None
    error_message: Optional[str] = None

class BucketOperationStatusResponse(BaseModel):
    id: str
    bucket_name: str
    source_prefix: str
    target_prefix: str
    source_lang: str
    target_lang: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    skipped_files: int
    files: Optional[list[FileOperationStatusResponse]] = None
