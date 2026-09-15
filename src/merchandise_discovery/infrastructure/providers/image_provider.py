"""Image-generation provider boundary, fixture adapter, and xAI implementation.

Stage 15 depends on this contract rather than an SDK. The default fixture provider creates
inspectable metadata only; the application storage adapter persists live provider binaries without
changing the stage or worker protocol.
"""

import re
from dataclasses import dataclass, field
from typing import Protocol

from openai import OpenAI, OpenAIError

from merchandise_discovery.domain.models.usage import UsageMetrics


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
    usage: UsageMetrics = field(default_factory=UsageMetrics)


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


class XAIImageProvider:
    """Generate merchandise artwork through xAI's OpenAI-compatible image endpoint."""

    def __init__(self, api_key: str, model: str = "grok-imagine-image", price_per_image: float = 0.02):
        self._client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        self._model = model
        self._price_per_image = price_per_image

    def generate(self, request: ImageGenerationRequest) -> GeneratedImage:
        """Submit one prompt and return the provider URL plus an estimated fixed image cost."""

        try:
            response = self._client.images.generate(model=self._model, prompt=request.prompt)
        except (OpenAIError, TypeError, ValueError) as error:
            raise RuntimeError("xAI image generation request failed.") from error
        if not response.data or not getattr(response.data[0], "url", None):
            raise RuntimeError("xAI image generation returned no image URL.")
        source_url = response.data[0].url
        slug = re.sub(r"[^a-z0-9]+", "-", request.concept_id.lower()).strip("-")
        return GeneratedImage(
            source_url=source_url,
            storage_key=f"xai-artwork/{slug}/variant-{request.variant_number}.png",
            width=1024,
            height=1024,
            mime_type="image/png",
            # xAI returns a hosted URL; Stage 15's storage adapter downloads it and replaces this
            # estimate with the measured binary size before MongoDB persistence.
            file_size_bytes=128_000,
            usage=UsageMetrics(
                provider="xai",
                model=self._model,
                request_count=1,
                image_count=1,
                estimated_cost_usd=self._price_per_image,
                cost_is_estimate=True,
                pricing_note="Estimated from configured xAI per-image pricing.",
            ),
        )
