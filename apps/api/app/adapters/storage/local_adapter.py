"""Filesystem storage adapter for local development and CI.

Implements the same `StorageAdapter` contract as S3 so no calling code changes.
Keys are treated as relative paths beneath a root directory, and every path is
confined to that root — a key containing traversal segments is refused rather
than escaping the sandbox (SECURITY.md §4).

Not for production: there are no signed URLs, no lifecycle rules, and no
durability guarantees. The factory only selects this in mock mode.
"""

from pathlib import Path

from app.adapters.storage.base import StorageAdapter
from app.config import settings


class LocalStorageError(Exception):
    """Raised when a key would escape the storage root."""


class LocalStorageAdapter(StorageAdapter):
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.mock_media_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if not candidate.is_relative_to(self.root):
            raise LocalStorageError("Storage key escapes the storage root.")
        return candidate

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        destination = self._resolve(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return key

    async def signed_url(self, key: str, expires_seconds: int = 3600) -> str:
        """Return a file URI.

        There is no signing to do locally; the expiry argument is accepted to
        satisfy the interface and is deliberately ignored.
        """
        return self._resolve(key).as_uri()

    async def delete(self, key: str) -> None:
        target = self._resolve(key)
        if target.exists():
            target.unlink()
