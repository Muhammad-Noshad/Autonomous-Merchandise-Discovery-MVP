"""Stage 15: generate artwork candidates through the injected image provider."""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import Artwork
from merchandise_discovery.domain.stages.stage_14_prompt_compilation import PromptCompilation
from merchandise_discovery.infrastructure.providers.image_provider import (
    ImageGenerationRequest,
    ImageProvider,
)


class ArtworkGenerationInput(BaseModel):
    """Finalist prompts and the configured number of image variants per concept."""

    prompts: list[PromptCompilation]
    artwork_variants_per_concept: int = Field(ge=1, le=10)


class ArtworkGenerationOutput(BaseModel):
    """Generated artwork metadata linked to concept, brief, and prompt."""

    artworks: list[Artwork]


def execute(
    input_data: ArtworkGenerationInput,
    provider: ImageProvider,
) -> ArtworkGenerationOutput:
    """Generate only finalist variants and retain every provider reference for review."""

    artworks: list[Artwork] = []
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
            artworks.append(
                Artwork(
                    run_id=prompt.run_id,
                    concept_id=prompt.concept_id,
                    brief_id=prompt.brief_id,
                    prompt=prompt.prompt,
                    storage_key=generated.storage_key,
                    source_url=generated.source_url,
                    width=generated.width,
                    height=generated.height,
                    mime_type=generated.mime_type,
                    file_size_bytes=generated.file_size_bytes,
                )
            )
    return ArtworkGenerationOutput(artworks=artworks)
