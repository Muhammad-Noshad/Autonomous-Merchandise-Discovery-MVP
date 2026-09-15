"""Tests for provider-backed stage execution boundaries."""

from unittest.mock import Mock

import pytest

from merchandise_discovery.application.discovery_stage_executor import DiscoveryStageExecutor
from merchandise_discovery.domain.models.artifacts import (
    IdentityIntersection,
    MerchandiseConcept,
    Niche,
    ResearchEvidence,
)
from merchandise_discovery.domain.models.usage import UsageMetrics
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun
from merchandise_discovery.domain.stages.stage_01_seed_discovery import SeedDiscoveryInput
from merchandise_discovery.domain.stages.stage_02_identity_expansion import (
    GeneratedDimension,
    IdentityExpansionInput,
    SeedExpansion,
    Stage2ReasoningOutput,
)
from merchandise_discovery.domain.stages.stage_02_identity_expansion import (
    execute as execute_identity_expansion,
)
from merchandise_discovery.domain.stages.stage_03_intersection_generation import (
    IntersectionGenerationInput,
    IntersectionProposal,
    Stage3ReasoningOutput,
    identity_ref,
)
from merchandise_discovery.domain.stages.stage_03_intersection_generation import (
    execute as execute_intersections,
)
from merchandise_discovery.domain.stages.stage_04_coherence_hypothesis import CoherenceInput
from merchandise_discovery.domain.stages.stage_07_experience_mining import (
    ExperienceMiningInput,
    ExperienceSignal,
    MinedExperienceSignal,
    Stage7ReasoningOutput,
)
from merchandise_discovery.domain.stages.stage_08_opportunity_scoring import (
    OpportunityEvaluation,
    OpportunityScoreInput,
    Stage8ReasoningOutput,
)
from merchandise_discovery.domain.stages.stage_09_concept_generation import ConceptGenerationInput
from merchandise_discovery.domain.stages.stage_10_concept_critique import ConceptCritiqueInput
from merchandise_discovery.infrastructure.providers.reasoning_provider import StructuredResponse
from merchandise_discovery.shared.seed_loader import load_seed_fixture


def test_stage_01_does_not_call_reasoning_provider() -> None:
    """Stage 1 remains a deterministic MongoDB selection even in live-provider mode."""

    seed_repository = Mock()
    seed_repository.list_all.return_value = load_seed_fixture()
    reasoning_provider = Mock()
    executor = DiscoveryStageExecutor(
        seed_repository,
        *(Mock() for _ in range(9)),
        reasoning_provider=reasoning_provider,
    )
    run = WorkflowRun(title="Stage 1 deterministic test")
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Autonomous Seed Discovery",
    )
    input_data = SeedDiscoveryInput(
        seed_source=run.config.seed_source,
        max_seed_items=12,
        selection_seed=run.config.selection_seed,
    ).model_dump(mode="python")

    result = executor.execute(run, stage, input_data)

    reasoning_provider.complete_structured.assert_not_called()
    assert result.usage.total_tokens == 0
    assert result.usage.estimated_cost_usd == 0
    assert result.output_data["model"] == "deterministic"


def test_stage_02_calls_structured_provider_and_preserves_usage() -> None:
    """Stage 2 sends the dedicated response model to the provider and returns its usage."""

    seed = load_seed_fixture()[0]
    dimensions = [
        GeneratedDimension(
            dimension_type=dimension_type,
            value=f"Generated {dimension_type}",
            confidence=0.8,
            merchandise_relevance=7,
            rationale="A concrete experience signal.",
        )
        for dimension_type in ("routine", "tension", "language", "ritual")
    ]
    provider_output = Stage2ReasoningOutput(
        expansions=[SeedExpansion(source_seed_id=seed.seed_id, dimensions=dimensions)],
        summary="Structured expansion summary.",
    )
    usage = UsageMetrics(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=100,
        output_tokens=80,
        total_tokens=180,
        estimated_cost_usd=0.00006,
        cost_is_estimate=True,
    )
    reasoning_provider = Mock()
    reasoning_provider.complete_structured.return_value = StructuredResponse(
        output=provider_output,
        usage=usage,
    )
    executor = DiscoveryStageExecutor(
        *(Mock() for _ in range(10)),
        reasoning_provider=reasoning_provider,
    )
    run = WorkflowRun(title="Stage 2 provider test")
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=2,
        stage_name="Identity Universe Expansion",
    )
    input_data = IdentityExpansionInput(selected_seeds=[seed]).model_dump(mode="python")

    result = executor.execute(run, stage, input_data)

    reasoning_provider.complete_structured.assert_called_once()
    assert (
        reasoning_provider.complete_structured.call_args.kwargs["response_model"].__name__
        == "Stage2ReasoningOutput"
    )
    assert result.usage == usage
    assert result.output_data["model"] == "gpt-4o-mini"
    assert len(result.output_data["identities"]) == 5


def test_stage_03_materializes_only_valid_provider_references() -> None:
    """Stage 3 uses all catalog identities as context but persists only valid proposals."""

    seeds = load_seed_fixture()
    expanded = execute_identity_expansion(IdentityExpansionInput(selected_seeds=seeds))
    audience = next(item for item in expanded.identities if item.category.value == "audience")
    interest = next(item for item in expanded.identities if item.category.value == "interest")
    value = next(item for item in expanded.identities if item.category.value == "value")
    dimension = next(
        item
        for item in expanded.identities
        if item.source_seed_id == audience.source_seed_id and item.dimension_type != "core"
    )
    valid_refs = [identity_ref(item) for item in (audience, dimension, interest, value)]
    reasoning = Stage3ReasoningOutput(
        proposals=[
            IntersectionProposal(
                identity_refs=valid_refs,
                composition_rationale="These identities share a recognizable work-life ritual.",
                distinctiveness=8,
            ),
            IntersectionProposal(
                identity_refs=["invented-ref", *valid_refs[1:]],
                composition_rationale="This proposal contains an identity outside the catalog.",
                distinctiveness=5,
            ),
        ],
        summary="One valid proposal and one rejected proposal.",
    )

    result = execute_intersections(
        IntersectionGenerationInput(identities=expanded.identities, max_intersections=10),
        run_id="run-test",
        reasoning_output=reasoning,
        model="gpt-4o-mini",
    )

    assert len(result.intersections) == 1
    assert result.provider_proposals_count == 2
    assert result.provider_rejected_count == 1
    intersection = result.intersections[0]
    assert intersection.metadata["generation_method"] == "provider"
    assert intersection.metadata["model"] == "gpt-4o-mini"
    assert intersection.metadata["composition_rationale"] == reasoning.proposals[0].composition_rationale
    assert intersection.metadata["identity_refs"] == valid_refs


def test_stage_03_calls_structured_provider_and_preserves_usage() -> None:
    """The executor sends the complete identity catalog to Stage 3 structured reasoning."""

    seeds = load_seed_fixture()
    expanded = execute_identity_expansion(IdentityExpansionInput(selected_seeds=seeds))
    audience = next(item for item in expanded.identities if item.category.value == "audience")
    interest = next(item for item in expanded.identities if item.category.value == "interest")
    value = next(item for item in expanded.identities if item.category.value == "value")
    provider_output = Stage3ReasoningOutput(
        proposals=[
            IntersectionProposal(
                identity_refs=[identity_ref(item) for item in (audience, interest, value)],
                composition_rationale="A focused three-axis merchandise audience.",
                distinctiveness=7,
            )
        ],
        summary="Generated a focused candidate.",
    )
    usage = UsageMetrics(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=600,
        output_tokens=100,
        total_tokens=700,
        estimated_cost_usd=0.00015,
        cost_is_estimate=True,
    )
    reasoning_provider = Mock()
    reasoning_provider.complete_structured.return_value = StructuredResponse(
        output=provider_output,
        usage=usage,
    )
    executor = DiscoveryStageExecutor(
        *(Mock() for _ in range(10)),
        reasoning_provider=reasoning_provider,
    )
    run = WorkflowRun(title="Stage 3 provider test")
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=3,
        stage_name="Intersection Generation",
    )
    input_data = IntersectionGenerationInput(
        identities=expanded.identities,
        max_intersections=10,
    ).model_dump(mode="python")

    result = executor.execute(run, stage, input_data)

    reasoning_provider.complete_structured.assert_called_once()
    assert (
        reasoning_provider.complete_structured.call_args.kwargs["response_model"].__name__
        == "Stage3ReasoningOutput"
    )
    assert result.usage == usage
    assert result.output_data["model"] == "gpt-4o-mini"
    assert result.output_data["provider_proposals_count"] == 1


def test_stage_07_calls_structured_provider_and_validates_evidence_lineage() -> None:
    """Stage 7 uses one typed AI response while retaining niche-owned evidence IDs."""

    niche = Niche(
        run_id="run-test",
        intersection_id="intersection-1",
        name="Remote worker gardeners",
        coherence_score=8.0,
        evidence_count=1,
        validated=True,
    )
    evidence = ResearchEvidence(
        run_id="run-test",
        niche_id=niche.niche_id,
        url="https://example.com/research",
        title="Audience ritual",
        source="Example",
        excerpt="People use a quiet ritual to decompress after demanding days.",
    )
    provider_output = Stage7ReasoningOutput(
        signals=[
            MinedExperienceSignal(
                niche_id=niche.niche_id,
                frustrations=["Need to decompress after demanding days."],
                rituals=["A repeatable evening reset ritual."],
                evidence_ids=[evidence.evidence_id],
                confidence=0.9,
                experience_summary="The audience repeatedly uses a decompression ritual after work.",
            )
        ],
        summary="Evidence-grounded experience signals.",
    )
    usage = UsageMetrics(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=120,
        output_tokens=80,
        total_tokens=200,
        estimated_cost_usd=0.000066,
        cost_is_estimate=True,
    )
    reasoning_provider = Mock()
    reasoning_provider.complete_structured.return_value = StructuredResponse(
        output=provider_output,
        usage=usage,
    )
    executor = DiscoveryStageExecutor(
        *(Mock() for _ in range(10)),
        reasoning_provider=reasoning_provider,
    )
    run = WorkflowRun(title="Stage 7 provider test")
    stage = StageExecution(run_id=run.run_id, stage_number=7, stage_name="Experience Mining")
    input_data = ExperienceMiningInput(niches=[niche], evidence=[evidence]).model_dump(mode="python")

    result = executor.execute(run, stage, input_data)

    reasoning_provider.complete_structured.assert_called_once()
    assert (
        reasoning_provider.complete_structured.call_args.kwargs["response_model"].__name__
        == "Stage7ReasoningOutput"
    )
    assert result.usage == usage
    assert result.output_data["model"] == "gpt-4o-mini"
    assert result.output_data["signals"][0]["evidence_ids"] == [evidence.evidence_id]


def test_stage_08_uses_ai_qualitative_scores_but_calculates_total() -> None:
    """Stage 8 keeps evidence strength and the weighted total under application control."""

    niche = Niche(
        run_id="run-test",
        intersection_id="intersection-1",
        name="Remote worker gardeners",
        coherence_score=8.0,
        evidence_count=3,
        validated=True,
    )
    signal = ExperienceSignal(
        niche_id=niche.niche_id,
        frustrations=["A recurring reset need."],
        evidence_ids=["evidence-1"],
        confidence=0.8,
        experience_summary="A recurring reset need is visible.",
    )
    provider_output = Stage8ReasoningOutput(
        evaluations=[
            OpportunityEvaluation(
                niche_id=niche.niche_id,
                experience_clarity=25,
                audience_fit=16,
                differentiation=14,
                rationale="The supplied signals describe a clear and specific use case.",
            )
        ],
        summary="Qualitative opportunity evaluation.",
    )
    usage = UsageMetrics(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=100,
        output_tokens=70,
        total_tokens=170,
        estimated_cost_usd=0.000057,
        cost_is_estimate=True,
    )
    reasoning_provider = Mock()
    reasoning_provider.complete_structured.return_value = StructuredResponse(
        output=provider_output,
        usage=usage,
    )
    executor = DiscoveryStageExecutor(
        *(Mock() for _ in range(10)),
        reasoning_provider=reasoning_provider,
    )
    run = WorkflowRun(title="Stage 8 provider test")
    stage = StageExecution(run_id=run.run_id, stage_number=8, stage_name="Opportunity Scoring")
    input_data = OpportunityScoreInput(niches=[niche], signals=[signal]).model_dump(mode="python")

    result = executor.execute(run, stage, input_data)

    reasoning_provider.complete_structured.assert_called_once()
    assert (
        reasoning_provider.complete_structured.call_args.kwargs["response_model"].__name__
        == "Stage8ReasoningOutput"
    )
    assert result.usage == usage
    score = result.output_data["scores"][0]
    assert score["evidence_strength"] == 30
    assert score["overall_score"] == 85
    assert result.output_data["model"] == "gpt-4o-mini"


def test_live_stage_09_provider_failure_is_not_converted_to_success() -> None:
    """A live provider outage propagates to stage-runner failure handling without fallback output."""

    niche = Niche(
        run_id="run-test",
        intersection_id="intersection-1",
        name="Remote worker gardeners",
        experience_summary="A recurring reset ritual is observed.",
        validated=True,
    )
    reasoning_provider = Mock()
    reasoning_provider.complete_structured.side_effect = RuntimeError("provider unavailable")
    executor = DiscoveryStageExecutor(
        *(Mock() for _ in range(10)),
        reasoning_provider=reasoning_provider,
    )
    run = WorkflowRun(title="Stage 9 provider failure test")
    stage = StageExecution(run_id=run.run_id, stage_number=9, stage_name="Concept Generation")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        executor.execute(
            run,
            stage,
            ConceptGenerationInput(niches=[niche], concepts_per_niche=1).model_dump(mode="python"),
        )


def test_live_stage_10_provider_failure_is_not_converted_to_success() -> None:
    """Stage 10 also exposes provider failure so the persisted stage is visibly failed."""

    concept = MerchandiseConcept(
        run_id="run-test",
        niche_id="niche-1",
        phrase="A specific reset ritual",
        description="A wearable expression of an observed experience.",
    )
    reasoning_provider = Mock()
    reasoning_provider.complete_structured.side_effect = RuntimeError("provider unavailable")
    executor = DiscoveryStageExecutor(
        *(Mock() for _ in range(10)),
        reasoning_provider=reasoning_provider,
    )
    run = WorkflowRun(title="Stage 10 provider failure test")
    stage = StageExecution(run_id=run.run_id, stage_number=10, stage_name="Concept Critique")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        executor.execute(
            run,
            stage,
            ConceptCritiqueInput(concepts=[concept]).model_dump(mode="python"),
        )


@pytest.mark.parametrize("stage_number", [2, 3, 4, 7, 8])
def test_reasoning_provider_failures_propagate_for_all_ai_stages(stage_number: int) -> None:
    """Every AI-backed stage exposes provider failures to durable stage error handling."""

    seed = load_seed_fixture()[0]
    if stage_number == 2:
        input_model = IdentityExpansionInput(selected_seeds=[seed])
    elif stage_number == 3:
        expanded = execute_identity_expansion(IdentityExpansionInput(selected_seeds=[seed]))
        input_model = IntersectionGenerationInput(
            identities=expanded.identities,
            max_intersections=10,
        )
    elif stage_number == 4:
        input_model = CoherenceInput(
            intersections=[
                IdentityIntersection(
                    run_id="run-test",
                    identities=["Remote workers", "Home gardeners"],
                )
            ]
        )
    else:
        niche = Niche(
            run_id="run-test",
            intersection_id="intersection-1",
            name="Remote worker gardeners",
            experience_summary="A recurring reset ritual is observed.",
            evidence_count=1,
            validated=True,
        )
        if stage_number == 7:
            evidence = ResearchEvidence(
                run_id="run-test",
                niche_id=niche.niche_id,
                url="https://example.com/research",
                title="Audience ritual",
                source="Example",
                excerpt="People use a quiet ritual to decompress.",
            )
            input_model = ExperienceMiningInput(niches=[niche], evidence=[evidence])
        else:
            input_model = OpportunityScoreInput(niches=[niche], signals=[ExperienceSignal(
                niche_id=niche.niche_id,
                evidence_ids=["evidence-1"],
                confidence=0.8,
                experience_summary="A recurring reset ritual is observed.",
            )])

    reasoning_provider = Mock()
    reasoning_provider.complete_structured.side_effect = RuntimeError("provider unavailable")
    executor = DiscoveryStageExecutor(
        *(Mock() for _ in range(10)),
        reasoning_provider=reasoning_provider,
    )
    run = WorkflowRun(title=f"Stage {stage_number} provider failure test")
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=stage_number,
        stage_name=f"Stage {stage_number}",
    )

    with pytest.raises(RuntimeError, match="provider unavailable"):
        executor.execute(run, stage, input_model.model_dump(mode="python"))
