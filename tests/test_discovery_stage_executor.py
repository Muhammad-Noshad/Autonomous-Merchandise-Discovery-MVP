"""Tests for provider-backed stage execution boundaries."""

from unittest.mock import Mock

from merchandise_discovery.application.discovery_stage_executor import DiscoveryStageExecutor
from merchandise_discovery.domain.models.usage import UsageMetrics
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun
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
from merchandise_discovery.infrastructure.providers.reasoning_provider import StructuredResponse
from merchandise_discovery.shared.seed_loader import load_seed_fixture


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
