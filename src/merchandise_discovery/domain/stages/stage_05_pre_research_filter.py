"""Stage 5: preserve the former filter slot as a compatibility pass-through.

Selection now belongs to Stage 4 because the AI must choose the exact research set. Stage 5 keeps
the historical stage number and output shape so persisted runs and old detail pages remain readable;
it performs no ranking, truncation, duplicate removal, or subjective quality filtering.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import IdentityIntersection


class PreResearchFilterInput(BaseModel):
    """Stage 4's complete candidate audit passed through for legacy consumers."""

    intersections: list[IdentityIntersection]
    selected_intersection_ids: list[str] = Field(default_factory=list)
    # Retained for payload compatibility. Stage 5 no longer uses this value to truncate candidates.
    max_intersections: int | None = Field(default=None, ge=1, le=5000)


class PreResearchFilterOutput(BaseModel):
    """The legacy accepted/rejected shape, now reflecting Stage 4's direct decision."""

    accepted: list[IdentityIntersection]
    rejected: list[IdentityIntersection]
    all_intersections: list[IdentityIntersection]


def execute(input_data: PreResearchFilterInput) -> PreResearchFilterOutput:
    """Pass through Stage 4's selected set without introducing a second selection decision."""

    selected_ids = set(input_data.selected_intersection_ids)
    if not selected_ids:
        selected_ids = {
            item.intersection_id
            for item in input_data.intersections
            if item.eligible_for_research
        }
    known_ids = {item.intersection_id for item in input_data.intersections}
    unknown = sorted(selected_ids - known_ids)
    if unknown:
        raise ValueError(f"Stage 5 received unknown selected intersection IDs: {unknown}.")

    accepted: list[IdentityIntersection] = []
    rejected: list[IdentityIntersection] = []
    all_intersections: list[IdentityIntersection] = []
    for intersection in input_data.intersections:
        if intersection.intersection_id in selected_ids:
            materialized = intersection.model_copy(
                update={"eligible_for_research": True, "filter_reason": None}
            )
            accepted.append(materialized)
        else:
            materialized = intersection.model_copy(
                update={
                    "eligible_for_research": False,
                    "filter_reason": intersection.filter_reason
                    or "Not selected by AI for the configured research budget.",
                }
            )
            rejected.append(materialized)
        all_intersections.append(materialized)
    return PreResearchFilterOutput(
        accepted=accepted,
        rejected=rejected,
        all_intersections=all_intersections,
    )
