"""Stage 11: optionally screen duplicate phrases before image generation.

This MVP check compares normalized phrases within the current run. It is not a semantic similarity
search, trademark search, or legal IP assessment; naming the stage as a duplicate screen keeps the
client-facing result honest while preserving a future provider insertion point.
"""

import re

from pydantic import BaseModel

from merchandise_discovery.domain.models.artifacts import MerchandiseConcept
from merchandise_discovery.domain.models.common import ConceptVerdict


class SimilarityCheckInput(BaseModel):
    """Critiqued concepts entering the optional duplicate screen."""

    concepts: list[MerchandiseConcept]


class SimilarityCheck(BaseModel):
    """Duplicate-screen result for one concept."""

    concept_id: str
    risk_level: str
    similar_to: str | None = None
    reason: str


class SimilarityCheckOutput(BaseModel):
    """All concepts and their optional-screen outcomes."""

    concepts: list[MerchandiseConcept]
    survivors: list[MerchandiseConcept]
    rejected: list[MerchandiseConcept]
    checks: list[SimilarityCheck]


def _normalized_phrase(phrase: str) -> str:
    """Normalize case, punctuation, and repeated whitespace for exact duplicate detection."""

    without_punctuation = re.sub(r"[^\w\s]+", " ", phrase.casefold(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", without_punctuation).strip()


def execute(input_data: SimilarityCheckInput) -> SimilarityCheckOutput:
    """Reject later duplicate phrases globally within this run, keeping the highest score."""

    seen: dict[str, MerchandiseConcept] = {}
    survivors: list[MerchandiseConcept] = []
    rejected: list[MerchandiseConcept] = []
    checks: list[SimilarityCheck] = []
    for concept in sorted(
        input_data.concepts,
        key=lambda item: (-(item.overall_score or 0), item.concept_id),
    ):
        key = _normalized_phrase(concept.phrase)
        original = seen.get(key)
        if original is None:
            seen[key] = concept
            survivors.append(concept)
            checks.append(
                SimilarityCheck(
                    concept_id=concept.concept_id,
                    risk_level="low",
                    reason="No duplicate phrase was found in the current run.",
                )
            )
            continue
        reason = f"Duplicate phrase detected; retained higher-scoring concept {original.concept_id}."
        rejected_concept = concept.model_copy(
            update={
                "verdict": ConceptVerdict.REJECT,
                "selected": False,
                "critique": {**concept.critique, "similarity_reason": reason},
            }
        )
        rejected.append(rejected_concept)
        checks.append(
            SimilarityCheck(
                concept_id=concept.concept_id,
                risk_level="high",
                similar_to=original.concept_id,
                reason=reason,
            )
        )
    concepts = survivors + rejected
    return SimilarityCheckOutput(
        concepts=concepts,
        survivors=survivors,
        rejected=rejected,
        checks=checks,
    )
