"""Stage 6: gather and preserve public evidence for candidate niches.

This module owns the transformation from accepted identity intersections to researched niche
records. Provider I/O is injected through a small protocol, keeping the stage portable and easy to
test with either fixture data or a future external research API.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import (
    IdentityIntersection,
    Niche,
    ResearchEvidence,
)
from merchandise_discovery.infrastructure.providers.research_provider import (
    ResearchDocument,
    ResearchProvider,
    ResearchRequest,
)


class NicheResearchInput(BaseModel):
    """Eligible intersections and the configured research bound for one run."""

    intersections: list[IdentityIntersection]
    max_researched_niches: int = Field(ge=1, le=100)


class NicheResearchOutput(BaseModel):
    """Research targets, source-backed evidence, and the resulting niche records."""

    niches: list[Niche]
    evidence: list[ResearchEvidence]
    selected_intersection_ids: list[str]


def _ordered_targets(input_data: NicheResearchInput) -> list[IdentityIntersection]:
    """Select the strongest eligible intersections using stable score and ID tie-breakers."""

    return sorted(
        (item for item in input_data.intersections if item.eligible_for_research),
        key=lambda item: (-(item.coherence_score or 0), item.intersection_id),
    )[: input_data.max_researched_niches]


def _to_evidence(
    document: ResearchDocument,
    *,
    run_id: str,
    niche_id: str,
) -> ResearchEvidence:
    """Attach workflow ownership to a provider-neutral source record."""

    return ResearchEvidence(
        run_id=run_id,
        niche_id=niche_id,
        url=document.url,
        title=document.title,
        source=document.source,
        excerpt=document.excerpt,
        evidence_type=document.evidence_type,
    )


def execute(
    input_data: NicheResearchInput,
    provider: ResearchProvider,
    *,
    run_id: str,
) -> NicheResearchOutput:
    """Research bounded targets and return fully provenance-linked niche artifacts.

    An empty provider response is retained as an unvalidated niche rather than treated as proof of
    failure. This distinction lets later scoring show that a candidate lacked evidence.
    """

    niches: list[Niche] = []
    evidence: list[ResearchEvidence] = []
    selected_ids: list[str] = []
    for intersection in _ordered_targets(input_data):
        niche = Niche(
            run_id=run_id,
            intersection_id=intersection.intersection_id,
            name=" + ".join(intersection.identities),
            coherence_score=intersection.coherence_score,
        )
        documents = provider.search(
            ResearchRequest(
                query=" ".join(intersection.identities),
                identities=tuple(intersection.identities),
                hypotheses=tuple(intersection.experience_hypotheses),
            )
        )
        niche_evidence = [
            _to_evidence(document, run_id=run_id, niche_id=niche.niche_id)
            for document in documents
        ]
        niches.append(niche.model_copy(update={"evidence_count": len(niche_evidence), "validated": bool(niche_evidence)}))
        evidence.extend(niche_evidence)
        selected_ids.append(intersection.intersection_id)

    return NicheResearchOutput(
        niches=niches,
        evidence=evidence,
        selected_intersection_ids=selected_ids,
    )
