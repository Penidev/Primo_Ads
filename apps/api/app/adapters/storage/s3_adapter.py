"""S3 / R2-compatible object storage adapter.

All user assets are private: objects are written without public ACLs and are
only ever read through short-lived presigned URLs (SECURITY.md §8).
"""

import asyncio
from functools import partial

import boto3
from botocore.config import Config

from app.adapters.storage.base import StorageAdapter
from app.config import settings


class S3StorageAdapter(StorageAdapter):
    def __init__(self) -> None:
        if not settings.aws_s3_bucket:
            raise RuntimeError("AWS_S3_BUCKET is not configured.")
        self.bucket = settings.aws_s3_bucket
        self._client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            config=Config(signature_version="s3v4"),
        )

    async def _run(self, func, *args, **kwargs):
        """Run blocking boto3 calls off the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        await self._run(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            # No ACL argument: objects stay private by default.
            ServerSideEncryption="AES256",
        )
        return key

    async def signed_url(self, key: str, expires_seconds: int = 3600) -> str:
        return await self._run(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )

    async def delete(self, key: str) -> None:
        await self._run(self._client.delete_object, Bucket=self.bucket, Key=key)
