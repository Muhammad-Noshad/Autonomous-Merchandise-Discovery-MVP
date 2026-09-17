"""Shared final artwork-results stage for both pipeline variants.

The MVP ends with a visual results gallery. It deliberately does not mutate artwork decisions or
create human-review records; visual review is a post-run UI concern rather than a workflow gate.
"""

from pydantic import BaseModel

from merchandise_discovery.domain.models.artifacts import Artwork
from merchandise_discovery.domain.stages.stage_16_artwork_critique import ArtworkEvaluation


class ArtworkGalleryInput(BaseModel):
    """Artwork and deterministic evaluations received from the preceding critique stage."""

    artworks: list[Artwork]
    evaluations: list[ArtworkEvaluation]


class ArtworkGalleryOutput(BaseModel):
    """Persisted result snapshot consumed by the final UI gallery."""

    artworks: list[Artwork]
    evaluations: list[ArtworkEvaluation]
    summary: str = ""


def execute(input_data: ArtworkGalleryInput) -> ArtworkGalleryOutput:
    """Pass through all QA results so the final stage can display every image."""

    return ArtworkGalleryOutput(
        artworks=input_data.artworks,
        evaluations=input_data.evaluations,
        summary=f"Displayed {len(input_data.artworks)} artwork candidates for visual review.",
    )
