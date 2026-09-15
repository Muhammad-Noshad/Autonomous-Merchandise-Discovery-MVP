"""Stage 10: critique each merchandise concept with one structured evaluation.

OpenAI supplies bounded component judgments and qualitative weaknesses. This module owns the
integrity boundary: it requires exactly one evaluation per input concept, calculates the weighted
overall score, and derives the keep/reject verdict locally. The deterministic evaluator remains
available for fixture mode, but live provider failures are intentionally allowed to fail the stage
so the UI does not present fallback output as successful AI work.
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
    personal_recognition: float = Field(ge=0, le=10)
    niche_specificity: float = Field(ge=0, le=10)
    visual_distinctiveness: float = Field(ge=0, le=10)
    overall_score: float = Field(ge=0, le=10)
    verdict: ConceptVerdict
    weaknesses: list[str] = Field(default_factory=list)
    rationale: str


class ConceptCritiqueProposal(BaseModel):
    """Provider critique without application-owned overall score or verdict."""

    concept_id: str = Field(min_length=1)
    authenticity: float = Field(ge=0, le=10)
    clarity: float = Field(ge=0, le=10)
    wearability: float = Field(ge=0, le=10)
    commercial_potential: float = Field(ge=0, le=10)
    personal_recognition: float = Field(ge=0, le=10)
    niche_specificity: float = Field(ge=0, le=10)
    visual_distinctiveness: float = Field(ge=0, le=10)
    weaknesses: list[str] = Field(default_factory=list, max_length=8)
    rationale: str = Field(min_length=1, max_length=500)


class Stage10ReasoningOutput(BaseModel):
    """Exact structured response expected from OpenAI for Stage 10."""

    evaluations: list[ConceptCritiqueProposal] = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=500)


class ConceptCritiqueOutput(BaseModel):
    """Concepts updated with their critique and a separate evaluation record per candidate."""

    concepts: list[MerchandiseConcept]
    evaluations: list[ConceptEvaluation]
    summary: str = ""
    model: str = "deterministic"


def _evaluate(
    concept: MerchandiseConcept,
    proposal: ConceptCritiqueProposal | None = None,
) -> ConceptEvaluation:
    """Calculate the final score and verdict from deterministic policy-owned rules."""

    if proposal is None:
        phrase_words = len(concept.phrase.split())
        authenticity = 8.0 if "experience" in concept.description.lower() else 6.5
        clarity = round(min(10.0, max(5.0, 11 - phrase_words * 0.8)), 2)
        wearability = 8.0 if phrase_words <= 5 else 6.0
        commercial_potential = 8.0 if any(
            word in concept.phrase.lower() for word in ("reset", "ritual", "relief", "belonging")
        ) else 6.5
        personal_recognition = 8.0 if concept.recognizable_moment and concept.insider_behavior_or_language else 5.0
        niche_specificity = concept.specificity_score or 5.0
        visual_distinctiveness = 8.0 if concept.visual_hook else 5.0
        weaknesses: list[str] = []
        rationale = (
            "The concept scored across authenticity, clarity, wearability, "
            "and commercial potential using deterministic rules."
        )
    else:
        authenticity = round(proposal.authenticity, 2)
        clarity = round(proposal.clarity, 2)
        wearability = round(proposal.wearability, 2)
        commercial_potential = round(proposal.commercial_potential, 2)
        personal_recognition = round(proposal.personal_recognition, 2)
        niche_specificity = round(proposal.niche_specificity, 2)
        visual_distinctiveness = round(proposal.visual_distinctiveness, 2)
        weaknesses = list(dict.fromkeys(proposal.weaknesses))
        rationale = proposal.rationale.strip()
    overall = round((authenticity + clarity + wearability + commercial_potential) / 4, 2)
    if clarity < 7:
        weaknesses.append("The phrase may need simplification for quick visual comprehension.")
    if commercial_potential < 7:
        weaknesses.append("The commercial hook is not yet distinctive enough.")
    if personal_recognition < 7:
        weaknesses.append("The concept does not describe a personally recognizable audience moment.")
    if niche_specificity < 7:
        weaknesses.append("The concept is too broad to feel owned by a specific niche.")
    if visual_distinctiveness < 7:
        weaknesses.append("The visual hook is not distinctive enough to guide artwork generation.")
    weaknesses = list(dict.fromkeys(weaknesses))
    verdict = (
        ConceptVerdict.KEEP
        if overall >= 6
        and personal_recognition >= 7
        and niche_specificity >= 7
        and visual_distinctiveness >= 7
        else ConceptVerdict.REJECT
    )
    return ConceptEvaluation(
        concept_id=concept.concept_id,
        authenticity=authenticity,
        clarity=clarity,
        wearability=wearability,
        commercial_potential=commercial_potential,
        personal_recognition=personal_recognition,
        niche_specificity=niche_specificity,
        visual_distinctiveness=visual_distinctiveness,
        overall_score=overall,
        verdict=verdict,
        weaknesses=weaknesses,
        rationale=rationale,
    )


def _validate_provider_links(
    input_data: ConceptCritiqueInput,
    reasoning_output: Stage10ReasoningOutput,
) -> dict[str, ConceptCritiqueProposal]:
    """Require exactly one provider evaluation for every input concept."""

    expected_ids = {concept.concept_id for concept in input_data.concepts}
    returned_ids = [evaluation.concept_id for evaluation in reasoning_output.evaluations]
    if len(returned_ids) != len(set(returned_ids)):
        raise ValueError("Stage 10 provider output contains duplicate concept IDs.")
    returned_id_set = set(returned_ids)
    unknown_ids = returned_id_set - expected_ids
    missing_ids = expected_ids - returned_id_set
    if unknown_ids:
        raise ValueError(f"Stage 10 provider output contains unknown concept IDs: {sorted(unknown_ids)}.")
    if missing_ids:
        raise ValueError(f"Stage 10 provider output is missing concept IDs: {sorted(missing_ids)}.")
    return {evaluation.concept_id: evaluation for evaluation in reasoning_output.evaluations}


def execute(
    input_data: ConceptCritiqueInput,
    reasoning_output: Stage10ReasoningOutput | None = None,
    model: str = "deterministic",
) -> ConceptCritiqueOutput:
    """Attach one provider or deterministic critique to every generated concept."""

    proposals_by_id = (
        _validate_provider_links(input_data, reasoning_output)
        if reasoning_output is not None
        else {}
    )
    evaluations = [_evaluate(concept, proposals_by_id.get(concept.concept_id)) for concept in input_data.concepts]
    evaluation_by_id = {evaluation.concept_id: evaluation for evaluation in evaluations}
    concepts = [
        concept.model_copy(
            update={
                "scores": {
                    "authenticity": evaluation.authenticity,
                    "clarity": evaluation.clarity,
                    "wearability": evaluation.wearability,
                    "commercial_potential": evaluation.commercial_potential,
                    "personal_recognition": evaluation.personal_recognition,
                    "niche_specificity": evaluation.niche_specificity,
                    "visual_distinctiveness": evaluation.visual_distinctiveness,
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
    return ConceptCritiqueOutput(
        concepts=concepts,
        evaluations=evaluations,
        summary=reasoning_output.summary if reasoning_output is not None else "",
        model=model,
    )
