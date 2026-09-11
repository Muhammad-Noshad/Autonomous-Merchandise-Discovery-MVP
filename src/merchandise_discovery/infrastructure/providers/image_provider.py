"""Image-generation provider boundary and deterministic local implementation.

Stage 15 depends on this contract rather than an SDK. The default fixture provider creates
inspectable metadata only; an xAI implementation can later return real object-storage references
without changing the stage or the worker protocol.
"""

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ImageGenerationRequest:
    """Prompt and variant identity supplied to an image provider."""

    concept_id: str
    brief_id: str
    prompt: str
    variant_number: int


@dataclass(frozen=True)
class GeneratedImage:
    """Provider-neutral image metadata returned before it becomes an Artwork artifact."""

    source_url: str
    storage_key: str
    width: int
    height: int
    mime_type: str
    file_size_bytes: int


class ImageProvider(Protocol):
    """Contract implemented by fixture and future xAI image providers."""

    def generate(self, request: ImageGenerationRequest) -> GeneratedImage:
        """Generate one candidate and return metadata for durable storage."""


class FixtureImageProvider:
    """Return deterministic image-shaped metadata without network calls or API credits."""

    def generate(self, request: ImageGenerationRequest) -> GeneratedImage:
        """Create a stable fixture reference for one concept/variant pair."""

        slug = re.sub(r"[^a-z0-9]+", "-", request.concept_id.lower()).strip("-")
        storage_key = f"fixture-artwork/{slug}/variant-{request.variant_number}.png"
        return GeneratedImage(
            source_url=f"https://fixture.local/artwork/{slug}/{request.variant_number}.png",
            storage_key=storage_key,
            width=1024,
            height=1024,
            mime_type="image/png",
            file_size_bytes=128_000,
        )
