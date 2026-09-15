"""Object-storage boundary for generated artwork files.

The image provider returns a short-lived provider URL, while MongoDB stores only metadata. This
module owns the durable binary boundary so the provider can later be replaced with S3 or Cloudinary
without changing Stage 15 or the review UI. The MVP uses a local filesystem adapter in live mode;
fixture URLs intentionally remain reference-only and never trigger a network call.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class StoredArtwork:
    """Durable storage result returned to the stage that creates artwork metadata."""

    storage_key: str
    file_size_bytes: int


class ArtworkStorage(Protocol):
    """Provider-neutral contract for persisting one generated image binary."""

    def persist(
        self,
        *,
        source_url: str,
        storage_key: str,
        reported_size_bytes: int,
    ) -> StoredArtwork:
        """Persist the provider object and return its stable key and measured size."""


class ReferenceArtworkStorage:
    """Keep deterministic fixture metadata usable without pretending a binary was downloaded."""

    def persist(
        self,
        *,
        source_url: str,
        storage_key: str,
        reported_size_bytes: int,
    ) -> StoredArtwork:
        """Return the fixture reference unchanged and perform no network operation."""

        return StoredArtwork(storage_key=storage_key, file_size_bytes=reported_size_bytes)


class LocalArtworkStorage:
    """Download live provider images into an application-owned local object-store directory."""

    def __init__(self, root: str | Path = ".artifacts"):
        self._root = Path(root).resolve()

    def persist(
        self,
        *,
        source_url: str,
        storage_key: str,
        reported_size_bytes: int,
    ) -> StoredArtwork:
        """Download one provider URL using a traversal-safe key and atomically publish the file."""

        relative_key = Path(storage_key)
        if relative_key.is_absolute() or ".." in relative_key.parts:
            raise ValueError("Artwork storage key must be a relative path without parent traversal.")
        if source_url.startswith("https://fixture.local/"):
            return StoredArtwork(storage_key=storage_key, file_size_bytes=reported_size_bytes)

        request = Request(source_url, headers={"User-Agent": "autonomous-merchandise-discovery/0.1"})
        try:
            with urlopen(request, timeout=30) as response:  # URL is provider output.
                content = response.read()
        except (OSError, ValueError) as error:
            raise RuntimeError("Artwork object storage download failed.") from error
        if not content:
            raise RuntimeError("Artwork object storage received an empty file.")

        target = self._root / relative_key
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        return StoredArtwork(storage_key=storage_key, file_size_bytes=len(content))
