"""Stage 17: apply Luna's targeted artwork corrections through Grok.

This stage is deliberately one-way: Luna evaluates the original artwork, then Grok edits only
the candidates Luna flags. The edited result is persisted as the final candidate, while Stage 16's
snapshot remains the immutable record of what was originally reviewed.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import Artwork
from merchandise_discovery.domain.models.common import ArtworkDecision
from merchandise_discovery.domain.models.usage import UsageMetrics, combine_usage
from merchandise_discovery.domain.stages.stage_16_artwork_critique import ArtworkEvaluation
from merchandise_discovery.infrastructure.providers.image_provider import (
    ImageEditRequest,
    ImageProvider,
)
from merchandise_discovery.infrastructure.storage import ArtworkStorage, ReferenceArtworkStorage


class ArtworkRevisionInput(BaseModel):
    """Original artwork candidates and Luna evaluations from the preceding stage."""

    artworks: list[Artwork]
    evaluations: list[ArtworkEvaluation]


class ArtworkRevision(BaseModel):
    """Audit record describing the before/after image references for one candidate."""

    artwork_id: str
    revised: bool
    edit_prompt: str | None = None
    status: str
    # These references are captured before the final Artwork record is updated to Grok's output,
    # making a durable visual comparison possible without duplicating the image binary in MongoDB.
    original_source_url: str | None = None
    original_storage_key: str | None = None
    original_width: int | None = None
    original_height: int | None = None
    original_mime_type: str | None = None
    original_file_size_bytes: int | None = None


class ArtworkRevisionOutput(BaseModel):
    """Final artwork candidates plus revision audit records and provider usage."""

    artworks: list[Artwork]
    evaluations: list[ArtworkEvaluation]
    revisions: list[ArtworkRevision]
    usage: UsageMetrics = Field(default_factory=UsageMetrics)


def execute(
    input_data: ArtworkRevisionInput,
    provider: ImageProvider,
    storage: ArtworkStorage | None = None,
) -> ArtworkRevisionOutput:
    """Edit flagged candidates, retain accepted candidates, and preserve the original evaluations."""

    evaluations_by_id = {evaluation.artwork_id: evaluation for evaluation in input_data.evaluations}
    artwork_ids = {artwork.artwork_id for artwork in input_data.artworks}
    if set(evaluations_by_id) != artwork_ids:
        raise ValueError("Artwork revision requires exactly one evaluation per artwork.")

    storage_adapter = storage or ReferenceArtworkStorage()
    artworks: list[Artwork] = []
    revisions: list[ArtworkRevision] = []
    usages: list[UsageMetrics] = []
    for artwork in input_data.artworks:
        evaluation = evaluations_by_id[artwork.artwork_id]
        original_reference = {
            "original_source_url": artwork.source_url,
            "original_storage_key": artwork.storage_key,
            "original_width": artwork.width,
            "original_height": artwork.height,
            "original_mime_type": artwork.mime_type,
            "original_file_size_bytes": artwork.file_size_bytes,
        }
        if evaluation.decision == ArtworkDecision.ACCEPT:
            artworks.append(artwork)
            revisions.append(
                ArtworkRevision(
                    artwork_id=artwork.artwork_id,
                    revised=False,
                    status="unchanged",
                    **original_reference,
                )
            )
            continue
        if evaluation.decision == ArtworkDecision.REJECT:
            # Rejected candidates stay in the final snapshot so the results page can compare
            # what survived the review/edit path with what Luna explicitly removed.
            artworks.append(artwork)
            revisions.append(
                ArtworkRevision(
                    artwork_id=artwork.artwork_id,
                    revised=False,
                    status="rejected",
                    **original_reference,
                )
            )
            continue
        if not evaluation.edit_prompt:
            raise ValueError(f"Artwork {artwork.artwork_id} is flagged but has no Grok edit prompt.")
        if not artwork.source_url:
            raise ValueError(f"Artwork {artwork.artwork_id} has no source URL for Grok editing.")

        edited = provider.edit(
            ImageEditRequest(
                artwork_id=artwork.artwork_id,
                source_url=artwork.source_url,
                prompt=evaluation.edit_prompt,
            )
        )
        stored = storage_adapter.persist(
            source_url=edited.source_url,
            storage_key=edited.storage_key,
            reported_size_bytes=edited.file_size_bytes,
        )
        usages.append(edited.usage)
        artworks.append(
            artwork.model_copy(
                update={
                    "source_url": edited.source_url,
                    "storage_key": stored.storage_key,
                    "width": edited.width,
                    "height": edited.height,
                    "mime_type": edited.mime_type,
                    "file_size_bytes": stored.file_size_bytes,
                    "revision_prompt": evaluation.edit_prompt,
                    "revision_number": artwork.revision_number + 1,
                    # There is intentionally no second Luna verdict. Clearing the old decision
                    # prevents the final gallery from presenting an edited image as re-verified.
                    "decision": None,
                    "critique": {
                        **artwork.critique,
                        "revision_status": "edited_without_reverification",
                    },
                }
            )
        )
        revisions.append(
            ArtworkRevision(
                artwork_id=artwork.artwork_id,
                revised=True,
                edit_prompt=evaluation.edit_prompt,
                status="edited_without_reverification",
                **original_reference,
            )
        )

    return ArtworkRevisionOutput(
        artworks=artworks,
        evaluations=input_data.evaluations,
        revisions=revisions,
        usage=combine_usage(*usages),
    )
