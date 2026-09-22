"""Stage 2 contract for turning social-behavior candidates into Grok image requests.

Stage 1 owns the reasoning: it extracts the behavior, writes the merchandise copy, and creates
the visual prompt. This module only validates that handoff and maps it to the shared image
generation contract, keeping provider and storage concerns outside the social pipeline.
"""

from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field

from merchandise_discovery.domain.pipelines.social_behavior_text.pipeline import (
    SocialBehaviorTextCandidate,
)
from merchandise_discovery.domain.stages.stage_14_prompt_compilation import PromptCompilation
from merchandise_discovery.domain.stages.stage_15_artwork_generation import (
    ArtworkGenerationInput,
    ArtworkGenerationOutput,
)
from merchandise_discovery.domain.stages.stage_15_artwork_generation import (
    execute as execute_artwork_generation,
)
from merchandise_discovery.infrastructure.providers.image_provider import ImageProvider
from merchandise_discovery.infrastructure.storage import ArtworkStorage


class SocialArtworkInput(BaseModel):
    """Stage 1 candidates and the number of images to create for each candidate."""

    candidates: list[SocialBehaviorTextCandidate] = Field(min_length=1, max_length=25)
    artwork_variants_per_candidate: int = Field(default=1, ge=1, le=3)


def _stable_id(run_id: str, source_url: str, index: int, kind: str) -> str:
    """Create repeatable artifact IDs so a retry replaces the same social candidate records."""

    return str(uuid5(NAMESPACE_URL, f"social-behavior:{run_id}:{source_url}:{index}:{kind}"))


def to_artwork_generation_input(
    input_model: SocialArtworkInput,
    *,
    run_id: str,
) -> ArtworkGenerationInput:
    """Map social candidates to the shared Grok generation input without changing their meaning."""

    prompts: list[PromptCompilation] = []
    for index, candidate in enumerate(input_model.candidates, start=1):
        prompt = candidate.artwork_prompt.strip()
        # Provider output is expected to include the exact copy, but this guard prevents a malformed
        # prompt from producing an image that silently omits the merchandise text.
        if candidate.artwork_text not in prompt:
            prompt = f'{prompt}\nExact merchandise text to render: "{candidate.artwork_text}".'
        prompts.append(
            PromptCompilation(
                run_id=run_id,
                concept_id=_stable_id(run_id, candidate.source_url, index, "concept"),
                brief_id=_stable_id(run_id, candidate.source_url, index, "brief"),
                prompt=prompt,
                combination_name=candidate.artwork_text,
            )
        )
    return ArtworkGenerationInput(
        prompts=prompts,
        artwork_variants_per_concept=input_model.artwork_variants_per_candidate,
    )


def execute(
    input_model: SocialArtworkInput,
    *,
    run_id: str,
    provider: ImageProvider,
    storage: ArtworkStorage | None = None,
) -> ArtworkGenerationOutput:
    """Generate and persist social artwork through the shared provider-neutral stage contract."""

    return execute_artwork_generation(
        to_artwork_generation_input(input_model, run_id=run_id),
        provider,
        storage,
    )
