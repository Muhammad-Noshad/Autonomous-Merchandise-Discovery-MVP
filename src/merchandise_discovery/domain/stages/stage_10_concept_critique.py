"""Stage 10: critique each merchandise concept with one structured evaluation.

Critique output is deterministic in the MVP and stored on each concept. The criteria mirror the
future structured reasoning response, making a later provider-backed implementation a replaceable
stage dependency rather than a UI or persistence rewrite.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import MerchandiseConcept
from merchandise_discovery.domain.models.common import ConceptVerdict


class ConceptCritiqueInput(BaseModel):
    """Generated concept candidates awaiting evaluation."""

    concepts: list[MerchandiseConcept]


class ConceptEvaluation(BaseModel):
    """Inspectable critique values and decision rationale for one concept."""

    concept_id: str
    authenticity: float = Field(ge=0, le=10)
    clarity: float = Field(ge=0, le=10)
    wearability: float = Field(ge=0, le=10)
    commercial_potential: float = Field(ge=0, le=10)
    overall_score: float = Field(ge=0, le=10)
    verdict: ConceptVerdict
    weaknesses: list[str] = Field(default_factory=list)
    rationale: str


class ConceptCritiqueOutput(BaseModel):
    """Concepts updated with their critique and a separate evaluation record per candidate."""

    concepts: list[MerchandiseConcept]
    evaluations: list[ConceptEvaluation]


def _evaluate(concept: MerchandiseConcept) -> ConceptEvaluation:
    """Score transparent concept traits and reject candidates below the 6.0 threshold."""

    phrase_words = len(concept.phrase.split())
    authenticity = 8.0 if "experience" in concept.description.lower() else 6.5
    clarity = round(min(10.0, max(5.0, 11 - phrase_words * 0.8)), 2)
    wearability = 8.0 if phrase_words <= 5 else 6.0
    commercial_potential = 8.0 if any(
        word in concept.phrase.lower() for word in ("reset", "ritual", "relief", "belonging")
    ) else 6.5
    overall = round((authenticity + clarity + wearability + commercial_potential) / 4, 2)
    weaknesses: list[str] = []
    if clarity < 7:
        weaknesses.append("The phrase may need simplification for quick visual comprehension.")
    if commercial_potential < 7:
        weaknesses.append("The commercial hook is not yet distinctive enough.")
    verdict = ConceptVerdict.KEEP if overall >= 6 else ConceptVerdict.REJECT
    rationale = (
        f"The concept scored {overall:.2f}/10 across authenticity, clarity, wearability, "
        "and commercial potential."
    )
    return ConceptEvaluation(
        concept_id=concept.concept_id,
        authenticity=authenticity,
        clarity=clarity,
        wearability=wearability,
        commercial_potential=commercial_potential,
        overall_score=overall,
        verdict=verdict,
        weaknesses=weaknesses,
        rationale=rationale,
    )


def execute(input_data: ConceptCritiqueInput) -> ConceptCritiqueOutput:
    """Attach one reproducible critique to every generated concept."""

    evaluations = [_evaluate(concept) for concept in input_data.concepts]
    evaluation_by_id = {evaluation.concept_id: evaluation for evaluation in evaluations}
    concepts = [
        concept.model_copy(
            update={
                "scores": {
                    "authenticity": evaluation.authenticity,
                    "clarity": evaluation.clarity,
                    "wearability": evaluation.wearability,
                    "commercial_potential": evaluation.commercial_potential,
                },
                "overall_score": evaluation.overall_score,
                "verdict": evaluation.verdict,
                "critique": {
                    "weaknesses": evaluation.weaknesses,
                    "rationale": evaluation.rationale,
                },
            }
        )
        for concept in input_data.concepts
        if (evaluation := evaluation_by_id[concept.concept_id])
    ]
    return ConceptCritiqueOutput(concepts=concepts, evaluations=evaluations)
