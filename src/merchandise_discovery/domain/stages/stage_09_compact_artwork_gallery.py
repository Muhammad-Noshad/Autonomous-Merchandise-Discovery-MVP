"""Compact Stage 9: expose the generated artwork results without reviewer decisions.

The compact MVP ends with a visual results gallery. It deliberately does not mutate artwork
decisions or create human-review records; those approval rules remain owned by the baseline
pipeline until the A/B comparison has produced enough evidence to justify adding them here.
"""

from pydantic import BaseModel

from merchandise_discovery.domain.models.artifacts import Artwork
from merchandise_discovery.domain.stages.stage_16_artwork_critique import ArtworkEvaluation


class ArtworkGalleryInput(BaseModel):
    """QA-passed artwork and deterministic evaluations received from compact Stage 8."""

    artworks: list[Artwork]
    evaluations: list[ArtworkEvaluation]


class ArtworkGalleryOutput(BaseModel):
    """Persisted result snapshot consumed by the compact Stage 9 UI gallery."""

    artworks: list[Artwork]
    evaluations: list[ArtworkEvaluation]
    summary: str = ""


def execute(input_data: ArtworkGalleryInput) -> ArtworkGalleryOutput:
    """Pass through all QA results so the final compact stage can display every image."""

    return ArtworkGalleryOutput(
        artworks=input_data.artworks,
        evaluations=input_data.evaluations,
        summary=f"Displayed {len(input_data.artworks)} artwork candidates for visual review.",
    )
