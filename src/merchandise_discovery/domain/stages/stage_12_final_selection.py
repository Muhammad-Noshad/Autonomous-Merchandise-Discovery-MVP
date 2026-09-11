"""Stage 12: rank surviving concepts and select finalists."""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import MerchandiseConcept
from merchandise_discovery.domain.models.common import ConceptVerdict


class FinalSelectionInput(BaseModel):
    """Critiqued concepts, optionally screened, and the run-level finalist bound."""

    concepts: list[MerchandiseConcept]
    max_finalists: int = Field(ge=1, le=50)


class FinalSelectionOutput(BaseModel):
    """All ranked concepts plus the selected finalist subset."""

    concepts: list[MerchandiseConcept]
    finalists: list[MerchandiseConcept]
    rejected: list[MerchandiseConcept]


def execute(input_data: FinalSelectionInput) -> FinalSelectionOutput:
    """Select the strongest kept concepts with stable score and ID tie-breaking."""

    ordered = sorted(
        input_data.concepts,
        key=lambda item: (-(item.overall_score or 0), item.concept_id),
    )
    eligible = [
        concept
        for concept in ordered
        if concept.verdict == ConceptVerdict.KEEP
    ]
    finalist_ids = {concept.concept_id for concept in eligible[: input_data.max_finalists]}
    concepts: list[MerchandiseConcept] = []
    finalists: list[MerchandiseConcept] = []
    rejected: list[MerchandiseConcept] = []
    finalist_rank = 0
    for concept in ordered:
        selected = concept.concept_id in finalist_ids
        if selected:
            finalist_rank += 1
        updated = concept.model_copy(
            update={"selected": selected, "rank": finalist_rank if selected else None}
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
    )
