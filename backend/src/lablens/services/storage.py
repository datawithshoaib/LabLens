"""Private object storage adapters for local development and S3 deployments."""

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import boto3
from botocore.config import Config as BotoConfig

from lablens.core.config import Settings, get_settings


class ObjectStorage(Protocol):
    async def put(self, key: str, content: bytes, media_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


class FilesystemStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if candidate.parent != self.root:
            raise ValueError("Invalid object key")
        return candidate

    async def put(self, key: str, content: bytes, media_type: str) -> None:
        path = self._path(key)
        await asyncio.to_thread(self._write_new, path, content)

    @staticmethod
    def _write_new(path: Path, content: bytes) -> None:
        with path.open("xb") as target:
            target.write(content)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)

    async def delete(self, key: str) -> None:
        path = self._path(key)
        await asyncio.to_thread(path.unlink, missing_ok=True)


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.storage_bucket
        if not self.bucket:
            raise ValueError("STORAGE_BUCKET is required for S3 storage")
        self.encryption = settings.storage_server_side_encryption
        self.kms_key_id = settings.storage_kms_key_id
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint_url,
            region_name=settings.storage_region,
            config=BotoConfig(retries={"max_attempts": 4, "mode": "standard"}),
        )

    async def put(self, key: str, content: bytes, media_type: str) -> None:
        options: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": content,
            "ContentType": media_type,
            "ServerSideEncryption": self.encryption,
        }
        if self.encryption == "aws:kms" and self.kms_key_id:
            options["SSEKMSKeyId"] = self.kms_key_id
        await asyncio.to_thread(self.client.put_object, **options)

    async def get(self, key: str) -> bytes:
        response = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
        body = response["Body"]
        try:
            return await asyncio.to_thread(body.read)
        finally:
            await asyncio.to_thread(body.close)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)


@lru_cache(maxsize=1)
def get_storage() -> ObjectStorage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    return FilesystemStorage(settings.storage_dir)
