"""Tests for the behavior-first, identity-grounded social pipeline."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from merchandise_discovery.application.discovery_stage_executor import DiscoveryStageExecutor
from merchandise_discovery.application.stage_executor import StageResult
from merchandise_discovery.application.stage_quality_gate import (
    StageQualityError,
    validate_stage_result,
)
from merchandise_discovery.domain.models.common import IdentityType, PipelineVariant, SocialSource
from merchandise_discovery.domain.models.usage import UsageMetrics
from merchandise_discovery.domain.models.workflow import RunConfig, StageExecution, WorkflowRun
from merchandise_discovery.domain.pipelines.social_behavior_identity import pipeline
from merchandise_discovery.domain.stages.registry import stage_definitions_for
from merchandise_discovery.infrastructure.providers.image_provider import FixtureImageProvider


def _executor(stage_repository: Mock) -> DiscoveryStageExecutor:
    return DiscoveryStageExecutor(
        *(Mock() for _ in range(2)),
        stage_repository,
        *(Mock() for _ in range(7)),
    )


def _run(*, auto_identity: bool = False, auto_topic: bool = False) -> WorkflowRun:
    return WorkflowRun(
        title="Behavior-first identity run",
        config=RunConfig(
            pipeline_variant=PipelineVariant.SOCIAL_BEHAVIOR_IDENTITY,
            social_sources=[SocialSource.REDDIT],
            social_identity="bedside nurses" if not auto_identity else "",
            social_identity_type=IdentityType.OCCUPATION if not auto_identity else None,
            social_auto_identity=auto_identity,
            social_query="documenting chaotic patient encounters" if not auto_topic else "",
            social_auto_topic=auto_topic,
            social_candidate_count=2,
        ),
    )


def _live_output(input_model: pipeline.BehaviorIdentityInput) -> pipeline.BehaviorIdentityOutput:
    fixture = pipeline.execute(input_model)
    candidate = fixture.candidates[0].model_copy(
        update={
            "source_url": "https://reddit.com/r/nursing/comments/example/charting-encounter",
            "source_title": "Nurses describe charting difficult encounters",
            "source_excerpt": "A nurse describes translating an upsetting patient interaction into an objective chart note.",
            "audience_context": "Bedside nurses documenting difficult patient encounters.",
            "artwork_text": "I'm Not Being Rude. I'm Quoting the Patient Verbatim.",
        }
    )
    return pipeline.BehaviorIdentityOutput(
        identity_selected="Bedside nurses",
        identity_type_selected=IdentityType.OCCUPATION,
        identity_evidence="The cited nursing discussion describes bedside staff documenting patient encounters.",
        candidates=[candidate],
        search_summary="Nursing discussion about objective documentation.",
        topic_explored="documenting difficult patient encounters",
    )


def test_pipeline_registers_as_a_distinct_two_stage_variant() -> None:
    definitions = stage_definitions_for(PipelineVariant.SOCIAL_BEHAVIOR_IDENTITY)

    assert len(definitions) == 2
    assert "Behavior-First" in definitions[0].name
    assert "Identity-Grounded" in definitions[1].name


def test_prompt_discovers_behavior_before_selecting_identity() -> None:
    input_model = pipeline.BehaviorIdentityInput(
        sources=[SocialSource.REDDIT],
        auto_identity=True,
        auto_topic=True,
        candidate_count=3,
    )

    prompt = pipeline.build_user_prompt(input_model)

    assert prompt.index("Choose a concrete behavior") < prompt.index(
        "After you have established the behavior"
    )
    assert "one run-level identity" in prompt
    assert "identity_evidence" in prompt


def test_fixture_stage_one_exposes_selected_identity_and_behavior() -> None:
    run = _run()
    stage = StageExecution(run_id=run.run_id, stage_number=1, stage_name="Behavior first")
    executor = _executor(Mock())

    input_data = executor.prepare(run, stage)
    result = executor.execute(run, stage, input_data)

    assert result.output_data["identity_selected"] == "bedside nurses"
    assert result.output_data["identity_type_selected"] == IdentityType.OCCUPATION.value
    assert len(result.output_data["candidates"]) == 2
    assert result.usage.request_count == 0


def test_live_stage_one_makes_one_structured_search_request() -> None:
    run = _run(auto_identity=True, auto_topic=True)
    stage = StageExecution(run_id=run.run_id, stage_number=1, stage_name="Behavior first")
    provider = Mock()
    executor = _executor(Mock())
    executor._reasoning_provider = provider
    input_model = pipeline.BehaviorIdentityInput.model_validate(executor.prepare(run, stage))
    provider.complete_structured.return_value = SimpleNamespace(
        output=_live_output(input_model),
        usage=UsageMetrics(provider="openai", model="gpt-6-luna", request_count=1),
    )

    result = executor.execute(run, stage, input_model.model_dump(mode="python"))

    provider.complete_structured.assert_called_once()
    call = provider.complete_structured.call_args.kwargs
    assert call["response_model"] is pipeline.BehaviorIdentityOutput
    assert call["web_search_domains"] == ("reddit.com",)
    assert "first find a concrete" in call["system_prompt"]
    assert result.output_data["identity_selected"] == "Bedside nurses"
    assert result.usage.request_count == 1


def test_manual_identity_is_preserved_without_rejecting_provider_output() -> None:
    input_model = pipeline.BehaviorIdentityInput(
        sources=[SocialSource.REDDIT],
        identity="bedside nurses",
        identity_type=IdentityType.OCCUPATION,
        query="documenting difficult patient encounters",
        candidate_count=1,
    )
    provider_output = _live_output(input_model).model_copy(
        update={
            "identity_selected": "a different audience label",
            "identity_type_selected": IdentityType.ROLE,
        }
    )

    output = pipeline.execute(input_model, reasoning_output=provider_output, model="gpt-test")

    assert output.identity_selected == "bedside nurses"
    assert output.identity_type_selected is IdentityType.OCCUPATION


def test_stage_two_reuses_the_social_artwork_contract() -> None:
    run = _run()
    stage_one_output = pipeline.execute(
        pipeline.BehaviorIdentityInput(
            sources=[SocialSource.REDDIT],
            identity="bedside nurses",
            identity_type=IdentityType.OCCUPATION,
            query="documenting patient encounters",
            candidate_count=1,
        )
    )
    stage_repository = Mock()
    stage_repository.get_latest.return_value = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Behavior first",
        output_data=stage_one_output.model_dump(mode="python"),
    )
    executor = _executor(stage_repository)
    executor._image_provider = FixtureImageProvider()
    stage_two = StageExecution(run_id=run.run_id, stage_number=2, stage_name="Artwork Generation")

    input_data = executor.prepare(run, stage_two)
    result = executor.execute(run, stage_two, input_data)

    assert len(result.output_data["artworks"]) == 1
    assert result.output_data["artworks"][0]["source_url"].startswith("https://fixture.local/")


def test_quality_gate_requires_candidates_and_stage_two_artworks() -> None:
    run = _run()
    stage_one = StageExecution(run_id=run.run_id, stage_number=1, stage_name="Behavior first")
    stage_two = StageExecution(run_id=run.run_id, stage_number=2, stage_name="Artwork generation")

    validate_stage_result(
        run,
        stage_one,
        StageResult(
            input_data={},
            output_data={"candidates": [{"id": "one"}]},
            output_summary="stage one",
        ),
    )
    with pytest.raises(StageQualityError, match="candidates"):
        validate_stage_result(
            run,
            stage_one,
            StageResult(input_data={}, output_data={}, output_summary="empty"),
        )
    validate_stage_result(
        run,
        stage_two,
        StageResult(
            input_data={},
            output_data={"artworks": [{"id": "one"}]},
            output_summary="stage two",
        ),
    )
    with pytest.raises(StageQualityError, match="artworks"):
        validate_stage_result(
            run,
            stage_two,
            StageResult(input_data={}, output_data={}, output_summary="empty"),
        )
