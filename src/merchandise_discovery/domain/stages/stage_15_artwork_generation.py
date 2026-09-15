"""Stage 15: generate artwork candidates through the injected image provider."""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import Artwork
from merchandise_discovery.domain.models.usage import UsageMetrics, combine_usage
from merchandise_discovery.domain.stages.stage_14_prompt_compilation import PromptCompilation
from merchandise_discovery.infrastructure.providers.image_provider import (
    ImageGenerationRequest,
    ImageProvider,
)
from merchandise_discovery.infrastructure.storage import (
    ArtworkStorage,
    ReferenceArtworkStorage,
)


class ArtworkGenerationInput(BaseModel):
    """Finalist prompts and the configured number of image variants per concept."""

    prompts: list[PromptCompilation]
    artwork_variants_per_concept: int = Field(ge=1, le=10)


class ArtworkGenerationOutput(BaseModel):
    """Generated artwork metadata linked to concept, brief, and prompt."""

    artworks: list[Artwork]
    usage: UsageMetrics = Field(default_factory=UsageMetrics)


def execute(
    input_data: ArtworkGenerationInput,
    provider: ImageProvider,
    storage: ArtworkStorage | None = None,
) -> ArtworkGenerationOutput:
    """Generate finalist variants, persist binaries, and retain references for review."""

    artworks: list[Artwork] = []
    usages: list[UsageMetrics] = []
    storage_adapter = storage or ReferenceArtworkStorage()
    for prompt in input_data.prompts:
        for variant_number in range(1, input_data.artwork_variants_per_concept + 1):
            generated = provider.generate(
                ImageGenerationRequest(
                    concept_id=prompt.concept_id,
                    brief_id=prompt.brief_id,
                    prompt=prompt.prompt,
                    variant_number=variant_number,
                )
            )
            stored = storage_adapter.persist(
                source_url=generated.source_url,
                storage_key=generated.storage_key,
                reported_size_bytes=generated.file_size_bytes,
            )
            usages.append(generated.usage)
            artworks.append(
                Artwork(
                    run_id=prompt.run_id,
                    concept_id=prompt.concept_id,
                    brief_id=prompt.brief_id,
                    prompt=prompt.prompt,
                    storage_key=stored.storage_key,
                    source_url=generated.source_url,
                    width=generated.width,
                    height=generated.height,
                    mime_type=generated.mime_type,
                    file_size_bytes=stored.file_size_bytes,
                )
            )
    return ArtworkGenerationOutput(artworks=artworks, usage=combine_usage(*usages))
