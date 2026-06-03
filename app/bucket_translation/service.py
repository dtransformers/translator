import json
import logging
import boto3
from botocore.exceptions import ClientError
from typing import List, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION_NAME,
            endpoint_url=settings.S3_ENDPOINT_URL
        )

    def list_json_files(self, bucket_name: str, prefix: str) -> List[Dict[str, Any]]:
        """List all JSON files under a specific prefix in the bucket with metadata."""
        files = []
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if key.endswith('.json'):
                            files.append({
                                'Key': key,
                                'Size': obj.get('Size', 0),
                                'ETag': obj.get('ETag', '').strip('"')
                            })
        except ClientError:
            logger.exception("Error listing objects in bucket %s with prefix %s", bucket_name, prefix)
            raise
            
        return files

    def download_json(self, bucket_name: str, key: str) -> Dict[str, Any]:
        """Download and parse a JSON file from the bucket."""
        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=key)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except ClientError:
            logger.exception("Error downloading %s from %s", key, bucket_name)
            raise
        except json.JSONDecodeError:
            logger.exception("Error parsing JSON from %s", key)
            raise

    def upload_json(self, bucket_name: str, key: str, data: Dict[str, Any]) -> None:
        try:
            content = json.dumps(data, ensure_ascii=False, indent=2)
            self.s3_client.put_object(
                Bucket=bucket_name, 
                Key=key, 
                Body=content.encode('utf-8'),
                ContentType='application/json'
            )
        except ClientError:
            logger.exception("Error uploading %s to %s", key, bucket_name)
            raise

    def copy_object(self, source_bucket: str, source_key: str, dest_bucket: str, dest_key: str) -> None:
        try:
            self.s3_client.copy_object(
                Bucket=dest_bucket,
                Key=dest_key,
                CopySource={'Bucket': source_bucket, 'Key': source_key}
            )
        except ClientError:
            logger.exception("Error copying %s to %s", source_key, dest_key)
            raise
