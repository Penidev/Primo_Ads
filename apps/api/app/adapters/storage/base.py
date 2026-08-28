"""Storage adapter interface."""

from abc import ABC, abstractmethod


class StorageAdapter(ABC):
    """Abstract object storage. Implementations must never expose public URLs."""

    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Store bytes at `key`; return the storage key (not a public URL)."""

    @abstractmethod
    async def signed_url(self, key: str, expires_seconds: int = 3600) -> str:
        """Return a short-lived signed URL for reading the object."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove an object."""
