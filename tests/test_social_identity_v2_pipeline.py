"""Tests for the prompt-focused Identity V2 A/B pipeline."""

from types import SimpleNamespace
from unittest.mock import Mock

from merchandise_discovery.application.discovery_stage_executor import DiscoveryStageExecutor
from merchandise_discovery.domain.models.common import (
    IdentityType,
    PipelineVariant,
    SocialSource,
    StageStatus,
)
from merchandise_discovery.domain.models.usage import UsageMetrics
from merchandise_discovery.domain.models.workflow import RunConfig, StageExecution, WorkflowRun
from merchandise_discovery.domain.pipelines.social_identity_v2 import pipeline
from merchandise_discovery.domain.stages.registry import stage_definitions_for
from merchandise_discovery.infrastructure.providers.image_provider import FixtureImageProvider


def _executor(stage_repository: Mock) -> DiscoveryStageExecutor:
    """Construct the executor with doubles for the V2 stage boundaries."""

    return DiscoveryStageExecutor(
        *(Mock() for _ in range(2)),
        stage_repository,
        *(Mock() for _ in range(7)),
    )


def _run() -> WorkflowRun:
    """Build a manual-identity V2 run for isolated tests."""

    return WorkflowRun(
        title="Identity V2 fixture",
        config=RunConfig(
            pipeline_variant=PipelineVariant.SOCIAL_IDENTITY_V2,
            social_sources=[SocialSource.REDDIT],
            social_identity="bedside nurses",
            social_identity_type=IdentityType.OCCUPATION,
            social_query="translating chaotic patient encounters into objective chart language",
            social_candidate_count=2,
        ),
    )


def test_identity_v2_has_a_comparable_two_stage_sequence() -> None:
    """V2 keeps the same two visible stages while changing only Stage 1 prompting."""

    definitions = stage_definitions_for(PipelineVariant.SOCIAL_IDENTITY_V2)

    assert [(definition.number, definition.name) for definition in definitions] == [
        (1, "Identity V2 Prompt-Focused Social Behavior to Merchandise Text"),
        (2, "Identity V2 Social Merchandise Artwork Generation"),
    ]


def test_identity_v2_fixture_uses_the_shared_identity_contract() -> None:
    """Fixture mode exposes the same candidate shape as the identity-focused control."""

    run = _run()
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Identity V2 Prompt-Focused Social Behavior to Merchandise Text",
    )
    executor = _executor(Mock())

    input_data = executor.prepare(run, stage)
    result = executor.execute(run, stage, input_data)

    assert "dossier" not in result.output_data
    assert len(result.output_data["candidates"]) == 2
    assert "objective chart language" in result.output_data["candidates"][0]["artwork_text"].casefold()
    assert result.usage.request_count == 0


def test_identity_v2_uses_one_prompt_focused_provider_call() -> None:
    """Live Stage 1 makes one attributable call, matching the control pipeline's cost shape."""

    run = _run()
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Identity V2 Prompt-Focused Social Behavior to Merchandise Text",
    )
    fixture_output = pipeline.execute(
        pipeline.SocialIdentityV2Input(
            sources=[SocialSource.REDDIT],
            identity="bedside nurses",
            identity_type=IdentityType.OCCUPATION,
            query=run.config.social_query,
            candidate_count=1,
        )
    )
    candidate = fixture_output.candidates[0].model_copy(
        update={
            "source_url": "https://reddit.com/r/nursing/comments/example",
            "source_title": "Nursing discussion",
            "source_excerpt": "Nurses discuss quoting patients and documenting the encounter.",
            "artwork_text": "I'm Not Being Rude. I'm Quoting the Patient Verbatim.",
        }
    )
    provider_output = pipeline.SocialIdentityV2Output(
        identity_selected="bedside nurses",
        identity_type_selected=IdentityType.OCCUPATION,
        candidates=[candidate],
        search_summary="Source-backed nursing language.",
        topic_explored=run.config.social_query,
    )
    provider = Mock()
    provider.complete_structured.return_value = SimpleNamespace(
        output=provider_output,
        usage=UsageMetrics(provider="openai", model="gpt-5.6-luna", request_count=1),
    )
    executor = _executor(Mock())
    executor._reasoning_provider = provider

    result = executor.execute(run, stage, executor.prepare(run, stage))

    assert provider.complete_structured.call_count == 1
    call = provider.complete_structured.call_args.kwargs
    assert call["web_search_domains"] == ("reddit.com",)
    assert "self-explanatory" in call["system_prompt"]
    assert "IDENTITY: slogan" in call["system_prompt"]
    assert "two unmistakable contextual cues" in call["system_prompt"]
    assert "Target identity: bedside nurses" in call["user_prompt"]
    assert result.usage.request_count == 1
    assert result.output_data["candidates"][0]["artwork_text"].startswith("I'm Not Being Rude")


def test_identity_v2_auto_selection_receives_recent_identity_context() -> None:
    """Auto-selection prompts can avoid identities already used by recent completed runs."""

    run = _run()
    run.config.social_identity = ""
    run.config.social_identity_type = None
    run.config.social_auto_identity = True
    run.config.social_auto_topic = True
    previous_run = _run()
    previous_run.config.social_auto_identity = True
    previous_stage = StageExecution(
        run_id=previous_run.run_id,
        stage_number=1,
        stage_name="Identity V2 Prompt-Focused Social Behavior to Merchandise Text",
        status=StageStatus.COMPLETED,
        output_data={"identity_selected": "Home espresso hobbyist"},
    )
    run_repository = Mock()
    run_repository.list_recent.return_value = [previous_run]
    stage_repository = Mock()
    stage_repository.get_latest.return_value = previous_stage
    executor = _executor(stage_repository)
    executor._runs = run_repository

    stage = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Identity V2 Prompt-Focused Social Behavior to Merchandise Text",
    )
    input_data = executor.prepare(run, stage)

    assert input_data["recent_identity_selections"] == ["Home espresso hobbyist"]


def test_identity_v2_auto_selection_targets_lived_merchandise_situations() -> None:
    """Auto mode should frame topics as audience experiences, not research categories."""

    input_model = pipeline.SocialIdentityV2Input(
        sources=[SocialSource.REDDIT],
        auto_identity=True,
        auto_topic=True,
        candidate_count=3,
        recent_identity_selections=["Home espresso hobbyist"],
    )

    prompt = pipeline.build_user_prompt(input_model)

    assert "natural human identity label" in prompt
    assert "concrete incident, object, ritual" in prompt
    assert "hidden operational consequences" in prompt
    assert "research-report phrasing" in prompt
    assert "human situation, not a report heading" in prompt


def test_identity_v2_accepts_provider_typography_variant_for_ai_identity() -> None:
    """AI-selected identities tolerate dash/whitespace formatting without allowing semantic drift."""

    input_model = pipeline.SocialIdentityV2Input(
        sources=[SocialSource.REDDIT],
        auto_identity=True,
        auto_topic=True,
        candidate_count=1,
    )
    fixture_output = pipeline.execute(input_model)
    candidate = fixture_output.candidates[0].model_copy(
        update={
            "identity": "K-12 classroom teacher",
            "identity_type": IdentityType.OCCUPATION,
            "source_url": "https://reddit.com/r/Teachers/comments/example",
        }
    )
    provider_output = pipeline.SocialIdentityV2Output(
        identity_selected="K–12 classroom teacher",
        identity_type_selected=IdentityType.OCCUPATION,
        candidates=[candidate],
        search_summary="Source-backed classroom discussion.",
        topic_explored="classroom routines",
    )

    result = pipeline.execute(input_model, reasoning_output=provider_output, model="gpt-test")

    assert result.identity_selected == "K–12 classroom teacher"
    assert result.candidates[0].identity == "K–12 classroom teacher"


def test_identity_v2_reuses_the_control_artwork_prompt() -> None:
    """Stage 2 uses the same artwork path so the A/B test isolates Stage 1 prompts."""

    run = _run()
    stage_repository = Mock()
    stage_one = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Identity V2 Prompt-Focused Social Behavior to Merchandise Text",
        output_data=pipeline.execute(
            pipeline.SocialIdentityV2Input(
                sources=[SocialSource.REDDIT],
                identity="bedside nurses",
                identity_type=IdentityType.OCCUPATION,
                query=run.config.social_query,
                candidate_count=1,
            )
        ).model_dump(mode="python"),
    )
    stage_repository.get_latest.return_value = stage_one
    executor = _executor(stage_repository)
    executor._image_provider = FixtureImageProvider()

    stage_two = StageExecution(
        run_id=run.run_id,
        stage_number=2,
        stage_name="Identity V2 Social Merchandise Artwork Generation",
    )
    result = executor.execute(run, stage_two, executor.prepare(run, stage_two))

    assert len(result.output_data["artworks"]) == 1
    prompt = result.output_data["artworks"][0]["prompt"]
    assert "Identity evidence" in prompt
