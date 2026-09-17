"""Shared final artwork-results stage for both pipeline variants.

The MVP ends with a visual results gallery. It deliberately does not mutate artwork decisions or
create human-review records; visual review is a post-run UI concern rather than a workflow gate.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import Artwork
from merchandise_discovery.domain.stages.stage_16_artwork_critique import ArtworkEvaluation
from merchandise_discovery.domain.stages.stage_17_artwork_revision import ArtworkRevision


class ArtworkGalleryInput(BaseModel):
    """Final artwork and evaluations received from the critique/revision stages."""

    artworks: list[Artwork]
    evaluations: list[ArtworkEvaluation]
    revisions: list[ArtworkRevision] = Field(default_factory=list)


class ArtworkGalleryOutput(BaseModel):
    """Persisted result snapshot consumed by the final UI gallery."""

    artworks: list[Artwork]
    evaluations: list[ArtworkEvaluation]
    revisions: list[ArtworkRevision] = Field(default_factory=list)
    summary: str = ""


def execute(input_data: ArtworkGalleryInput) -> ArtworkGalleryOutput:
    """Pass through all QA results so the final stage can display every image."""

    return ArtworkGalleryOutput(
        artworks=input_data.artworks,
        evaluations=input_data.evaluations,
        revisions=input_data.revisions,
        summary=f"Displayed {len(input_data.artworks)} artwork candidates for visual review.",
    )
