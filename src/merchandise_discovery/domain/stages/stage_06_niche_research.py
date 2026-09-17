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
from merchandise_discovery.domain.models.usage import UsageMetrics, combine_usage
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
    usage: UsageMetrics = Field(default_factory=UsageMetrics)


def _ordered_targets(input_data: NicheResearchInput) -> list[IdentityIntersection]:
    """Research exactly the candidates handed over by Stage 4, preserving AI selection order."""

    targets = [item for item in input_data.intersections if item.eligible_for_research]
    if len(targets) > input_data.max_researched_niches:
        raise ValueError(
            "Stage 6 received more research targets than configured; "
            "selection must be completed by Stage 4."
        )
    return targets


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
    usages: list[UsageMetrics] = []
    for intersection in _ordered_targets(input_data):
        niche = Niche(
            run_id=run_id,
            intersection_id=intersection.intersection_id,
            name=" + ".join(intersection.identities),
            coherence_score=intersection.coherence_score,
        )
        search_result = provider.search(
            ResearchRequest(
                query=" ".join(intersection.identities),
                identities=tuple(intersection.identities),
                hypotheses=tuple(intersection.experience_hypotheses),
            )
        )
        documents = search_result.documents if hasattr(search_result, "documents") else search_result
        if hasattr(search_result, "usage"):
            usages.append(search_result.usage)
        niche_evidence = [
            _to_evidence(document, run_id=run_id, niche_id=niche.niche_id)
            for document in documents
        ]
        niches.append(
            niche.model_copy(
                update={
                    "evidence_count": len(niche_evidence),
                    "validated": bool(niche_evidence),
                    "research_summary": getattr(search_result, "summary", None) or None,
                }
            )
        )
        evidence.extend(niche_evidence)
        selected_ids.append(intersection.intersection_id)

    return NicheResearchOutput(
        niches=niches,
        evidence=evidence,
        selected_intersection_ids=selected_ids,
        usage=combine_usage(*usages),
    )
