"""Stage 12: compare surviving concepts and select the strongest finalists.

The reasoning provider supplies comparable qualitative dimensions in one batch. The application
validates coverage and computes the final score/ranking locally so provider output cannot silently
drop concepts or decide which records are persisted.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import MerchandiseConcept
from merchandise_discovery.domain.models.common import ConceptVerdict


class FinalSelectionInput(BaseModel):
    """Critiqued concepts, optionally screened, and the run-level finalist bound."""

    concepts: list[MerchandiseConcept]
    max_finalists: int = Field(ge=1, le=50)


class FinalSelectionEvaluation(BaseModel):
    """Provider comparison dimensions for one known concept."""

    concept_id: str = Field(min_length=1)
    distinctiveness: float = Field(ge=0, le=10)
    emotional_recognition: float = Field(ge=0, le=10)
    natural_wording: float = Field(ge=0, le=10)
    giftability: float = Field(ge=0, le=10)
    commercial_appeal: float = Field(ge=0, le=10)
    visual_potential: float = Field(ge=0, le=10)
    rationale: str = Field(min_length=1, max_length=800)


class Stage12ReasoningOutput(BaseModel):
    """Strict, batched AI response used as input to system-owned finalist selection."""

    evaluations: list[FinalSelectionEvaluation] = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=500)


class FinalSelectionOutput(BaseModel):
    """All ranked concepts plus the selected finalist subset."""

    concepts: list[MerchandiseConcept]
    finalists: list[MerchandiseConcept]
    rejected: list[MerchandiseConcept]
    evaluations: list[FinalSelectionEvaluation] = Field(default_factory=list)
    summary: str = ""
    model: str = "deterministic"


def execute(
    input_data: FinalSelectionInput,
    *,
    reasoning_output: Stage12ReasoningOutput | None = None,
    model: str = "deterministic",
) -> FinalSelectionOutput:
    """Validate comparison coverage, score locally, and select kept concepts deterministically."""

    concepts_by_id = {concept.concept_id: concept for concept in input_data.concepts}
    if len(concepts_by_id) != len(input_data.concepts):
        raise ValueError("Stage 12 input contains duplicate concept IDs.")

    scores: dict[str, float] = {}
    if reasoning_output is not None:
        evaluations_by_id = {item.concept_id: item for item in reasoning_output.evaluations}
        if len(evaluations_by_id) != len(reasoning_output.evaluations):
            raise ValueError("Stage 12 provider response contains duplicate concept IDs.")
        unknown = set(evaluations_by_id) - set(concepts_by_id)
        missing = set(concepts_by_id) - set(evaluations_by_id)
        if unknown:
            raise ValueError(f"Stage 12 provider response contains unknown concept IDs: {sorted(unknown)}")
        if missing:
            raise ValueError(f"Stage 12 provider response is missing concept IDs: {sorted(missing)}")
        for concept_id, evaluation in evaluations_by_id.items():
            dimensions = (
                evaluation.distinctiveness,
                evaluation.emotional_recognition,
                evaluation.natural_wording,
                evaluation.giftability,
                evaluation.commercial_appeal,
                evaluation.visual_potential,
            )
            scores[concept_id] = round(sum(dimensions) / len(dimensions), 2)
    else:
        scores = {
            concept.concept_id: round(concept.overall_score or 0, 2)
            for concept in input_data.concepts
        }

    ordered = sorted(
        input_data.concepts,
        key=lambda item: (-scores[item.concept_id], item.concept_id),
    )
    eligible = [
        concept
        for concept in ordered
        if concept.verdict == ConceptVerdict.KEEP
    ]
    finalist_ids = {concept.concept_id for concept in eligible[: input_data.max_finalists]}
    evaluation_by_id = {
        evaluation.concept_id: evaluation
        for evaluation in (reasoning_output.evaluations if reasoning_output else [])
    }
    concepts: list[MerchandiseConcept] = []
    finalists: list[MerchandiseConcept] = []
    rejected: list[MerchandiseConcept] = []
    finalist_rank = 0
    for concept in ordered:
        selected = concept.concept_id in finalist_ids
        if selected:
            finalist_rank += 1
        updated = concept.model_copy(
            update={
                "selected": selected,
                "rank": finalist_rank if selected else None,
                "selection_score": scores[concept.concept_id],
                "scores": (
                    {
                        **concept.scores,
                        **(
                            {
                                f"selection_{field}": getattr(
                                    evaluation_by_id[concept.concept_id], field
                                )
                                for field in (
                                    "distinctiveness",
                                    "emotional_recognition",
                                    "natural_wording",
                                    "giftability",
                                    "commercial_appeal",
                                    "visual_potential",
                                )
                            }
                            if concept.concept_id in evaluation_by_id
                            else {}
                        ),
                    }
                ),
            }
        )
        concepts.append(updated)
        if selected:
            finalists.append(updated)
        else:
            rejected.append(updated)
    return FinalSelectionOutput(
        concepts=concepts,
        finalists=finalists,
        rejected=rejected,
        evaluations=list(evaluation_by_id.values()),
        summary=(
            reasoning_output.summary
            if reasoning_output is not None
            else "Finalists ranked from Stage 10 scores by deterministic system selection."
        ),
        model=model,
    )
