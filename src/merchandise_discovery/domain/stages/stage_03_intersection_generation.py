"""Stage 3: generate bounded identity intersections with shared signals."""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import IdentityIntersection
from merchandise_discovery.domain.stages.stage_02_identity_expansion import ExpandedIdentity


class IntersectionGenerationInput(BaseModel):
    """Expanded identities and the configured candidate bound."""

    identities: list[ExpandedIdentity]
    max_intersections: int = Field(ge=1, le=5000)


class IntersectionGenerationOutput(BaseModel):
    """Candidate intersections retained for coherence scoring."""

    intersections: list[IdentityIntersection]


def _candidate(items: tuple[ExpandedIdentity, ...], run_id: str) -> IdentityIntersection:
    """Build a candidate and retain metadata needed to explain compatibility."""

    shared_tags = sorted(set.intersection(*(set(item.affinity_tags) for item in items)))
    identities = [item.value for item in items]
    source_ids = [item.source_seed_id for item in items]
    categories = [item.category for item in items]
    candidate_score = sum(item.priority for item in items) + len(shared_tags) * 5
    if len(items) == 3:
        candidate_score += 3
    return IdentityIntersection(
        run_id=run_id,
        identities=identities,
        source_seed_ids=source_ids,
        metadata={
            "categories": categories,
            "shared_tags": shared_tags,
            "candidate_score": candidate_score,
        },
    )


def execute(
    input_data: IntersectionGenerationInput,
    *,
    run_id: str,
) -> IntersectionGenerationOutput:
    """Generate audience-interest pairs and audience-interest-value triples in stable order."""

    cores = [identity for identity in input_data.identities if identity.dimension_type == "core"]
    groups: dict[str, list[ExpandedIdentity]] = {}
    for identity in cores:
        groups.setdefault(identity.category, []).append(identity)
    for group in groups.values():
        group.sort(key=lambda identity: (-identity.priority, identity.value.lower()))

    candidates: list[IdentityIntersection] = []
    for audience in groups.get("audience", []):
        for interest in groups.get("interest", []):
            candidates.append(_candidate((audience, interest), run_id))
            for value in groups.get("value", []):
                candidates.append(_candidate((audience, interest, value), run_id))

    candidates.sort(
        key=lambda candidate: (
            -int(candidate.metadata.get("candidate_score", 0)),
            "|".join(sorted(item.lower() for item in candidate.identities)),
        )
    )
    return IntersectionGenerationOutput(
        intersections=candidates[: input_data.max_intersections * 3]
    )
