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
