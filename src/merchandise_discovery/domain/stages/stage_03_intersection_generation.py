"""Stage 3: use bounded AI proposals to generate identity intersections.

This module owns the provider response contract and the deterministic safety boundary around it.
The application layer supplies the complete Stage 2 identity catalog to a reasoning provider, but
the provider can only refer to stable catalog references. The resulting intersections are built
from application-owned records, so AI cannot invent identities or bypass candidate limits.
"""

import hashlib
import re

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
    provider_proposals_count: int = Field(default=0, ge=0)
    provider_rejected_count: int = Field(default=0, ge=0)
    summary: str = ""
    model: str = "deterministic"


class IntersectionProposal(BaseModel):
    """One AI-proposed combination of references from the supplied identity catalog."""

    identity_refs: list[str] = Field(min_length=3, max_length=6)
    composition_rationale: str = Field(min_length=1, max_length=400)
    distinctiveness: int = Field(ge=1, le=10)


class Stage3ReasoningOutput(BaseModel):
    """Exact structured response expected from OpenAI for Stage 3."""

    proposals: list[IntersectionProposal] = Field(min_length=1, max_length=50)
    summary: str = Field(min_length=1, max_length=500)


def identity_ref(identity: ExpandedIdentity) -> str:
    """Return a stable, opaque reference for one identity value.

    Stage 3 sends these references instead of asking the provider to repeat full records. The hash
    prevents collisions when one seed contains multiple dimensions with the same type, while the
    readable prefix keeps provider prompts and persisted audit data inspectable.
    """

    normalized = " ".join(identity.value.casefold().split())
    value_hash = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    dimension = re.sub(r"[^a-z0-9]+", "_", identity.dimension_type.casefold()).strip("_")
    return f"{identity.source_seed_id}:{dimension}:{value_hash}"


def build_identity_catalog(identities: list[ExpandedIdentity]) -> list[dict]:
    """Serialize every selected Stage 2 identity into the provider's trusted reference catalog."""

    return [
        {
            "identity_ref": identity_ref(identity),
            "source_seed_id": identity.source_seed_id,
            "source_seed_name": identity.source_seed_name,
            "category": identity.category.value,
            "dimension_type": identity.dimension_type,
            "value": identity.value,
            "affinity_tags": identity.affinity_tags,
            "priority": identity.priority,
            "confidence": identity.confidence,
            "merchandise_relevance": identity.merchandise_relevance,
        }
        for identity in identities
    ]


def _candidate(
    items: tuple[ExpandedIdentity, ...],
    run_id: str,
    *,
    rationale: str | None = None,
    distinctiveness: int | None = None,
    model: str = "deterministic",
) -> IdentityIntersection:
    """Build a candidate and retain metadata needed to explain compatibility."""

    shared_tags = sorted(set.intersection(*(set(item.affinity_tags) for item in items)))
    identities = [item.value for item in items]
    source_ids = [item.source_seed_id for item in items]
    categories = [item.category.value for item in items]
    candidate_score = sum(item.priority for item in items) + len(shared_tags) * 5
    if len(items) == 3:
        candidate_score += 3
    if distinctiveness is not None:
        candidate_score += distinctiveness
    metadata = {
        "categories": categories,
        "shared_tags": shared_tags,
        "candidate_score": candidate_score,
        "identity_refs": [identity_ref(item) for item in items],
        "generation_method": "provider" if rationale else "deterministic",
        "model": model,
    }
    if rationale:
        metadata["composition_rationale"] = rationale
    if distinctiveness is not None:
        metadata["distinctiveness"] = distinctiveness
    return IdentityIntersection(
        run_id=run_id,
        identities=identities,
        source_seed_ids=source_ids,
        metadata=metadata,
    )


def _provider_candidate(
    proposal: IntersectionProposal,
    catalog: dict[str, ExpandedIdentity],
    run_id: str,
    *,
    model: str,
) -> IdentityIntersection:
    """Validate one provider proposal and materialize it from trusted application records."""

    refs = list(dict.fromkeys(proposal.identity_refs))
    if len(refs) != len(proposal.identity_refs):
        raise ValueError("Stage 3 provider proposal contains duplicate identity references.")
    missing_refs = [ref for ref in refs if ref not in catalog]
    if missing_refs:
        raise ValueError(f"Stage 3 provider proposal contains unknown identity refs: {missing_refs}.")

    items = tuple(catalog[ref] for ref in refs)
    categories = {item.category for item in items}
    if "audience" not in categories or "interest" not in categories:
        raise ValueError("Stage 3 provider proposal must include audience and interest identities.")
    if len({item.source_seed_id for item in items}) < 2:
        raise ValueError("Stage 3 provider proposal must combine at least two source seeds.")
    source_counts: dict[str, int] = {}
    for item in items:
        source_counts[item.source_seed_id] = source_counts.get(item.source_seed_id, 0) + 1
    if max(source_counts.values()) > 2:
        raise ValueError("Stage 3 provider proposal uses too many dimensions from one source seed.")

    return _candidate(
        items,
        run_id,
        rationale=proposal.composition_rationale,
        distinctiveness=proposal.distinctiveness,
        model=model,
    )


def execute(
    input_data: IntersectionGenerationInput,
    *,
    run_id: str,
    reasoning_output: Stage3ReasoningOutput | None = None,
    model: str = "deterministic",
) -> IntersectionGenerationOutput:
    """Materialize provider proposals, or generate deterministic candidates when no provider exists.

    Provider proposals are individually checked against the catalog. Invalid proposals are omitted
    rather than persisted; if none survive, raising ``ValueError`` fails the live stage so the
    provider problem remains visible to the operator.
    """

    if reasoning_output is not None:
        catalog = {identity_ref(identity): identity for identity in input_data.identities}
        candidates: list[IdentityIntersection] = []
        seen: set[str] = set()
        rejected = 0
        for proposal in reasoning_output.proposals:
            try:
                candidate = _provider_candidate(proposal, catalog, run_id, model=model)
            except ValueError:
                rejected += 1
                continue
            key = "|".join(sorted(identity_ref(catalog[ref]) for ref in proposal.identity_refs))
            if key in seen:
                rejected += 1
                continue
            seen.add(key)
            candidates.append(candidate)

        if not candidates:
            raise ValueError("Stage 3 provider returned no valid identity intersections.")
        candidates.sort(
            key=lambda candidate: (
                -int(candidate.metadata.get("candidate_score", 0)),
                candidate.intersection_id,
            )
        )
        return IntersectionGenerationOutput(
            intersections=candidates[: input_data.max_intersections * 3],
            provider_proposals_count=len(reasoning_output.proposals),
            provider_rejected_count=rejected,
            summary=reasoning_output.summary,
            model=model,
        )

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
        intersections=candidates[: input_data.max_intersections * 3],
    )
