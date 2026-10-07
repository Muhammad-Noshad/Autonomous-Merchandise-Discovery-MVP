"""Tests for the behavior-first, candidate-level identity pipeline."""

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


def _run(*, auto_topic: bool = False) -> WorkflowRun:
    return WorkflowRun(
        title="Behavior-first identity run",
        config=RunConfig(
            pipeline_variant=PipelineVariant.SOCIAL_BEHAVIOR_IDENTITY,
            social_sources=[SocialSource.REDDIT],
            social_query="documenting chaotic patient encounters" if not auto_topic else "",
            social_auto_topic=auto_topic,
            social_candidate_count=2,
        ),
    )


def _candidate(input_model: pipeline.BehaviorIdentityInput) -> pipeline.BehaviorIdentityCandidate:
    fixture = pipeline.execute(input_model).candidates[0]
    return fixture.model_copy(
        update={
            "identity": "Bedside nurses",
            "identity_type": IdentityType.OCCUPATION,
            "identity_evidence": "The discussion describes bedside nurses documenting difficult patient encounters.",
            "source_url": "https://reddit.com/r/nursing/comments/example/charting-encounter",
            "source_title": "Nurses describe charting difficult encounters",
            "source_excerpt": "A nurse describes translating an upsetting patient interaction into an objective chart note.",
            "audience_context": "Bedside nurses documenting difficult patient encounters.",
            "artwork_text": "I'm Not Being Rude. I'm Quoting the Patient Verbatim.",
        }
    )


def _live_output(input_model: pipeline.BehaviorIdentityInput) -> pipeline.BehaviorIdentityOutput:
    return pipeline.BehaviorIdentityOutput(
        candidates=[_candidate(input_model)],
        search_summary="Nursing discussion about objective documentation.",
        topic_explored="documenting difficult patient encounters",
    )


def test_pipeline_registers_as_a_distinct_two_stage_variant() -> None:
    definitions = stage_definitions_for(PipelineVariant.SOCIAL_BEHAVIOR_IDENTITY)

    assert len(definitions) == 2
    assert "Behavior-First" in definitions[0].name
    assert "Identity-Grounded" in definitions[1].name
    assert "each" in definitions[0].purpose


def test_prompt_maps_each_behavior_to_its_own_evidence_backed_identity() -> None:
    input_model = pipeline.BehaviorIdentityInput(
        sources=[SocialSource.REDDIT],
        auto_topic=True,
        candidate_count=3,
    )

    prompt = pipeline.build_user_prompt(input_model)
    instructions = pipeline.reasoning_instructions()

    assert "Choose a concrete behavior or topic yourself" in prompt
    assert "there is no single run-level target identity" in prompt
    assert "for each behavior" in instructions
    assert "do not force identity variety" in instructions


def test_fixture_stage_one_returns_identity_on_each_candidate() -> None:
    run = _run()
    stage = StageExecution(run_id=run.run_id, stage_number=1, stage_name="Behavior first")
    executor = _executor(Mock())

    input_data = executor.prepare(run, stage)
    result = executor.execute(run, stage, input_data)

    assert "identity" not in input_data
    assert "identity_selected" not in result.output_data
    assert len(result.output_data["candidates"]) == 2
    assert result.output_data["candidates"][0]["identity"]
    assert result.output_data["candidates"][0]["identity_evidence"]
    assert result.usage.request_count == 0


def test_live_stage_one_makes_one_structured_search_request() -> None:
    run = _run(auto_topic=True)
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
    assert "independently for each behavior" in call["system_prompt"]
    assert result.output_data["candidates"][0]["identity"] == "Bedside nurses"
    assert result.usage.request_count == 1


def test_provider_can_map_different_behaviors_to_different_identities() -> None:
    input_model = pipeline.BehaviorIdentityInput(
        sources=[SocialSource.REDDIT],
        query="people handling workday routines",
        candidate_count=2,
    )
    first = _candidate(input_model)
    second = first.model_copy(
        update={
            "identity": "Parents coordinating school mornings",
            "identity_type": IdentityType.ROLE,
            "identity_evidence": "The source describes a parent managing school drop-off before work.",
            "behavior": "A parent packs school bags before the household wakes up.",
            "source_url": "https://reddit.com/r/Parenting/comments/example/morning-routine",
        }
    )
    provider_output = pipeline.BehaviorIdentityOutput(
        candidates=[first, second],
        search_summary="Two distinct source-backed behaviors.",
    )

    output = pipeline.execute(input_model, reasoning_output=provider_output, model="gpt-test")

    assert [candidate.identity for candidate in output.candidates] == [
        "Bedside nurses",
        "Parents coordinating school mornings",
    ]


def test_previous_run_level_identity_output_can_still_resume_at_stage_two() -> None:
    input_model = pipeline.BehaviorIdentityInput(
        sources=[SocialSource.REDDIT],
        query="documenting difficult patient encounters",
        candidate_count=1,
    )
    old_candidate = _candidate(input_model).model_dump(mode="python")
    old_candidate.pop("identity")
    old_candidate.pop("identity_type")
    old_candidate.pop("identity_evidence")
    old_output = {
        "identity_selected": "Bedside nurses",
        "identity_type_selected": IdentityType.OCCUPATION,
        "identity_evidence": "Legacy evidence for the run-level identity.",
        "candidates": [old_candidate],
        "search_summary": "Historical Stage 1 output.",
    }

    migrated = pipeline.BehaviorIdentityOutput.model_validate(old_output)

    assert migrated.candidates[0].identity == "Bedside nurses"
    assert migrated.candidates[0].identity_type is IdentityType.OCCUPATION
    assert migrated.candidates[0].identity_evidence == "Legacy evidence for the run-level identity."


def test_stage_two_reuses_the_social_artwork_contract() -> None:
    run = _run()
    stage_one_output = pipeline.execute(
        pipeline.BehaviorIdentityInput(
            sources=[SocialSource.REDDIT],
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
            output_data={"candidates": [{"identity": "Audience"}]},
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
