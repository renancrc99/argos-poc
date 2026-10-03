"""Adaptador para S3 via boto3 (funciona com LocalStack)."""

import boto3
import structlog

from app.domain.exceptions import StorageError
from app.domain.ports.storage_port import StoragePort
from app.settings import settings

logger = structlog.get_logger()


class S3StorageAdapter(StoragePort):

    def __init__(self):
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.aws_endpoint_url,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_default_region,
        )

    async def upload_file(self, bucket: str, key: str, data: bytes) -> str:
        try:
            self._client.put_object(Bucket=bucket, Key=key, Body=data)
        except Exception as exc:
            raise StorageError(f"Falha ao enviar '{key}' para o bucket '{bucket}': {exc}") from exc
        logger.info("s3_upload", bucket=bucket, key=key, size=len(data))
        return key
