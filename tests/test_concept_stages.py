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
from merchandise_discovery.domain.stages.stage_12_final_selection import (
    FinalSelectionEvaluation,
    FinalSelectionInput,
    Stage12ReasoningOutput,
)
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
                    specific_audience="Remote workers who use a short end-of-day reset",
                    recognizable_moment="Closing the laptop and reclaiming ten quiet minutes",
                    insider_behavior_or_language="The small ritual after the last call",
                    emotional_tension="Wanting relief while still feeling mentally at work",
                    visual_hook="A laptop becoming a small doorway into quiet space",
                    audience_identification_reason="This moment is familiar to the researched audience.",
                    specificity_score=8,
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
                        specific_audience="An unsupported audience",
                        recognizable_moment="A specific unsupported moment",
                        insider_behavior_or_language="An unsupported insider cue",
                        emotional_tension="An unsupported tension",
                        visual_hook="An unsupported visual hook",
                        audience_identification_reason="Unsupported context.",
                        specificity_score=8,
                    )
                ],
                summary="Invalid proposal.",
            ),
        )


def test_provider_concept_failure_reports_specificity_reasons() -> None:
    """A failed niche explains the local quality gate instead of losing rejection context."""

    with pytest.raises(ValueError, match="below the minimum threshold of 7/10"):
        execute_generation(
            ConceptGenerationInput(niches=[_niche()], concepts_per_niche=1),
            reasoning_output=Stage9ReasoningOutput(
                concepts=[
                    ConceptProposal(
                        niche_id="niche-1",
                        phrase="A broad thought",
                        description="A generic concept.",
                        specific_audience="People with lifestyles",
                        recognizable_moment="A normal day",
                        insider_behavior_or_language="A broad phrase",
                        emotional_tension="Wanting something meaningful",
                        visual_hook="A generic symbol",
                        audience_identification_reason="It may resonate broadly.",
                        specificity_score=6.9,
                    )
                ],
                summary="One rejected concept.",
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
                    personal_recognition=3,
                    niche_specificity=3,
                    visual_distinctiveness=3,
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
    concepts = [concept.model_copy(update={"verdict": ConceptVerdict.KEEP}) for concept in concepts]
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
                        personal_recognition=8,
                        niche_specificity=8,
                        visual_distinctiveness=8,
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


def test_final_selection_computes_provider_score_and_preserves_lineage() -> None:
    """Stage 12 stores the locally combined score rather than trusting provider ranking."""

    concepts = execute_generation(
        ConceptGenerationInput(niches=[_niche()], concepts_per_niche=2)
    ).concepts
    concepts = [concept.model_copy(update={"verdict": ConceptVerdict.KEEP}) for concept in concepts]
    first_id, second_id = (concept.concept_id for concept in concepts)
    result = execute_selection(
        FinalSelectionInput(concepts=concepts, max_finalists=1),
        reasoning_output=Stage12ReasoningOutput(
            evaluations=[
                FinalSelectionEvaluation(
                    concept_id=first_id,
                    distinctiveness=9,
                    emotional_recognition=9,
                    natural_wording=8,
                    giftability=8,
                    commercial_appeal=9,
                    visual_potential=9,
                    rationale="Strong across the requested selection dimensions.",
                ),
                FinalSelectionEvaluation(
                    concept_id=second_id,
                    distinctiveness=5,
                    emotional_recognition=5,
                    natural_wording=6,
                    giftability=5,
                    commercial_appeal=5,
                    visual_potential=6,
                    rationale="Understandable but less distinctive.",
                ),
            ],
            summary="Compared two concepts.",
        ),
        model="gpt-4o-mini",
    )

    assert result.finalists[0].concept_id == first_id
    assert result.finalists[0].selection_score == 8.67
    assert result.model == "gpt-4o-mini"
    assert len(result.evaluations) == 2
