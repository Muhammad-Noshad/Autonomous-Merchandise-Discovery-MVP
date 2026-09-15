"""Tests for concept generation, critique, optional screening, and finalist selection."""

import pytest

from merchandise_discovery.domain.models.artifacts import MerchandiseConcept, Niche
from merchandise_discovery.domain.models.common import ConceptVerdict
from merchandise_discovery.domain.stages.stage_09_concept_generation import (
    ConceptGenerationInput,
    ConceptProposal,
    Stage9ReasoningOutput,
)
from merchandise_discovery.domain.stages.stage_09_concept_generation import (
    execute as execute_generation,
)
from merchandise_discovery.domain.stages.stage_10_concept_critique import (
    ConceptCritiqueInput,
    ConceptCritiqueProposal,
    Stage10ReasoningOutput,
)
from merchandise_discovery.domain.stages.stage_10_concept_critique import (
    execute as execute_critique,
)
from merchandise_discovery.domain.stages.stage_11_similarity_ip_check import SimilarityCheckInput
from merchandise_discovery.domain.stages.stage_11_similarity_ip_check import (
    execute as execute_similarity_check,
)
from merchandise_discovery.domain.stages.stage_12_final_selection import FinalSelectionInput
from merchandise_discovery.domain.stages.stage_12_final_selection import (
    execute as execute_selection,
)


def _niche() -> Niche:
    """Return a validated niche with the minimum evidence-backed concept context."""

    return Niche(
        niche_id="niche-1",
        run_id="run-test",
        intersection_id="intersection-1",
        name="Remote workers + Home gardeners",
        coherence_score=8.5,
        experience_summary="People need to decompress through a small, repeatable ritual.",
        evidence_count=3,
        validated=True,
    )


def test_concept_generation_is_experience_led_and_bounded() -> None:
    """Generation uses the validated experience and respects the configured per-niche limit."""

    result = execute_generation(ConceptGenerationInput(niches=[_niche()], concepts_per_niche=3))

    assert len(result.concepts) == 3
    assert all("observed experience" in concept.description for concept in result.concepts)
    assert all(concept.niche_id == "niche-1" for concept in result.concepts)


def test_provider_concept_proposals_receive_local_ids() -> None:
    """Stage 9 persists only validated-niche proposals and assigns IDs inside the application."""

    result = execute_generation(
        ConceptGenerationInput(niches=[_niche()], concepts_per_niche=2),
        reasoning_output=Stage9ReasoningOutput(
            concepts=[
                ConceptProposal(
                    niche_id="niche-1",
                    phrase="A specific reset ritual",
                    description="A wearable expression of the audience's observed reset ritual.",
                )
            ],
            summary="One validated concept proposal.",
        ),
        model="gpt-4o-mini",
    )

    assert len(result.concepts) == 1
    assert result.concepts[0].concept_id
    assert result.concepts[0].run_id == "run-test"
    assert result.model == "gpt-4o-mini"


def test_provider_concept_proposals_reject_non_validated_niches() -> None:
    """AI cannot create concepts for a niche that did not pass research validation."""

    invalid_niche = _niche().model_copy(update={"validated": False})
    with pytest.raises(ValueError, match="non-validated or unknown niche ID"):
        execute_generation(
            ConceptGenerationInput(niches=[invalid_niche], concepts_per_niche=1),
            reasoning_output=Stage9ReasoningOutput(
                concepts=[
                    ConceptProposal(
                        niche_id=invalid_niche.niche_id,
                        phrase="Unsupported concept",
                        description="This must not be persisted.",
                    )
                ],
                summary="Invalid proposal.",
            ),
        )


def test_critique_records_scores_and_verdicts() -> None:
    """Every concept receives the same inspectable criteria used to decide whether it survives."""

    generated = execute_generation(ConceptGenerationInput(niches=[_niche()], concepts_per_niche=2))
    result = execute_critique(ConceptCritiqueInput(concepts=generated.concepts))

    assert len(result.evaluations) == 2
    assert all(evaluation.verdict == ConceptVerdict.KEEP for evaluation in result.evaluations)
    assert all(concept.overall_score is not None for concept in result.concepts)
    assert all("authenticity" in concept.scores for concept in result.concepts)


def test_provider_critique_scores_and_verdict_are_calculated_locally() -> None:
    """Stage 10 uses AI components but owns the weighted overall score and threshold decision."""

    concept = execute_generation(ConceptGenerationInput(niches=[_niche()], concepts_per_niche=1)).concepts[0]
    result = execute_critique(
        ConceptCritiqueInput(concepts=[concept]),
        reasoning_output=Stage10ReasoningOutput(
            evaluations=[
                ConceptCritiqueProposal(
                    concept_id=concept.concept_id,
                    authenticity=2,
                    clarity=3,
                    wearability=4,
                    commercial_potential=5,
                    rationale="The concept is not sufficiently clear or distinctive.",
                )
            ],
            summary="One critique.",
        ),
        model="gpt-4o-mini",
    )

    assert result.evaluations[0].overall_score == 3.5
    assert result.evaluations[0].verdict == ConceptVerdict.REJECT
    assert result.concepts[0].overall_score == 3.5
    assert result.concepts[0].verdict == ConceptVerdict.REJECT
    assert result.model == "gpt-4o-mini"


def test_provider_critique_requires_exact_concept_coverage() -> None:
    """A partial provider response cannot silently drop a concept from the critique."""

    concepts = execute_generation(
        ConceptGenerationInput(niches=[_niche()], concepts_per_niche=2)
    ).concepts
    with pytest.raises(ValueError, match="missing concept IDs"):
        execute_critique(
            ConceptCritiqueInput(concepts=concepts),
            reasoning_output=Stage10ReasoningOutput(
                evaluations=[
                    ConceptCritiqueProposal(
                        concept_id=concepts[0].concept_id,
                        authenticity=8,
                        clarity=8,
                        wearability=8,
                        commercial_potential=8,
                        rationale="Only one concept was evaluated.",
                    )
                ],
                summary="No evaluations.",
            ),
        )


def test_similarity_check_rejects_lower_scoring_duplicate() -> None:
    """Duplicate screening retains the stronger candidate and records an actionable reason."""

    concepts = [
        MerchandiseConcept(
            concept_id="concept-high",
            run_id="run-test",
            niche_id="niche-1",
            phrase="Reset Mode",
            description="A specific reset experience.",
            overall_score=8.5,
            verdict=ConceptVerdict.KEEP,
        ),
        MerchandiseConcept(
            concept_id="concept-low",
            run_id="run-test",
            niche_id="niche-1",
            phrase="reset mode!",
            description="A duplicate reset experience.",
            overall_score=7.0,
            verdict=ConceptVerdict.KEEP,
        ),
    ]

    result = execute_similarity_check(SimilarityCheckInput(concepts=concepts))

    assert [concept.concept_id for concept in result.survivors] == ["concept-high"]
    assert result.rejected[0].verdict == ConceptVerdict.REJECT
    assert result.checks[1].similar_to == "concept-high"


def test_final_selection_assigns_stable_ranks_and_finalist_flags() -> None:
    """Selection chooses only kept concepts and exposes the chosen ranking on each finalist."""

    concepts = [
        MerchandiseConcept(
            concept_id="concept-b",
            run_id="run-test",
            niche_id="niche-1",
            phrase="Second",
            description="Second concept",
            overall_score=8.0,
            verdict=ConceptVerdict.KEEP,
        ),
        MerchandiseConcept(
            concept_id="concept-a",
            run_id="run-test",
            niche_id="niche-1",
            phrase="First",
            description="First concept",
            overall_score=8.0,
            verdict=ConceptVerdict.KEEP,
        ),
        MerchandiseConcept(
            concept_id="concept-rejected",
            run_id="run-test",
            niche_id="niche-1",
            phrase="Rejected",
            description="Rejected concept",
            overall_score=9.0,
            verdict=ConceptVerdict.REJECT,
        ),
    ]

    result = execute_selection(FinalSelectionInput(concepts=concepts, max_finalists=2))

    assert [concept.concept_id for concept in result.finalists] == ["concept-a", "concept-b"]
    assert [concept.rank for concept in result.finalists] == [1, 2]
    rejected = next(concept for concept in result.concepts if concept.concept_id == "concept-rejected")
    assert rejected.selected is False
