"""Stage 5: apply deterministic filtering before external research."""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import IdentityIntersection


class PreResearchFilterInput(BaseModel):
    """Scored intersections and the maximum number allowed into research."""

    intersections: list[IdentityIntersection]
    max_intersections: int = Field(ge=1, le=5000)


class PreResearchFilterOutput(BaseModel):
    """Accepted and rejected candidates, including the complete inspectable decision set."""

    accepted: list[IdentityIntersection]
    rejected: list[IdentityIntersection]
    all_intersections: list[IdentityIntersection]


def _canonical_key(intersection: IdentityIntersection) -> str:
    """Normalize identity order so duplicate candidates are deterministic."""

    return "|".join(sorted(identity.strip().lower() for identity in intersection.identities))


def execute(input_data: PreResearchFilterInput) -> PreResearchFilterOutput:
    """Reject duplicates, weak coherence, and candidates beyond the configured research bound."""

    ordered = sorted(
        input_data.intersections,
        key=lambda intersection: (
            -(intersection.coherence_score or 0),
            _canonical_key(intersection),
        ),
    )
    accepted: list[IdentityIntersection] = []
    rejected: list[IdentityIntersection] = []
    seen: set[str] = set()
    for intersection in ordered:
        key = _canonical_key(intersection)
        reason: str | None = None
        if key in seen:
            reason = "Rejected as a duplicate identity combination."
        elif (intersection.coherence_score or 0) < 6:
            reason = "Rejected because coherence score is below the 6.0 research threshold."
        elif len(accepted) >= input_data.max_intersections:
            reason = "Rejected because the configured research bound has been reached."

        if reason:
            rejected.append(
                intersection.model_copy(
                    update={"eligible_for_research": False, "filter_reason": reason}
                )
            )
        else:
            seen.add(key)
            accepted.append(
                intersection.model_copy(
                    update={"eligible_for_research": True, "filter_reason": None}
                )
            )

    all_intersections = accepted + rejected
    return PreResearchFilterOutput(
        accepted=accepted,
        rejected=rejected,
        all_intersections=all_intersections,
    )
