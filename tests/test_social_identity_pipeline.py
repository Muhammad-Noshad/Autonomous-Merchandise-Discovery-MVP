"""Tests for the identity-focused social A/B pipeline."""

from types import SimpleNamespace
from unittest.mock import Mock

from merchandise_discovery.application.discovery_stage_executor import DiscoveryStageExecutor
from merchandise_discovery.domain.models.common import IdentityType, PipelineVariant, SocialSource
from merchandise_discovery.domain.models.usage import UsageMetrics
from merchandise_discovery.domain.models.workflow import RunConfig, StageExecution, WorkflowRun
from merchandise_discovery.domain.pipelines.social_identity_focused import pipeline
from merchandise_discovery.domain.stages.registry import stage_definitions_for
from merchandise_discovery.infrastructure.providers.image_provider import FixtureImageProvider


def _executor(stage_repository: Mock) -> DiscoveryStageExecutor:
    """Construct the executor with doubles; identity stages use only stage and provider ports."""

    return DiscoveryStageExecutor(
        *(Mock() for _ in range(2)),
        stage_repository,
        *(Mock() for _ in range(7)),
    )


def _run() -> WorkflowRun:
    """Build one explicit identity-focused run configuration for isolated stage tests."""

    return WorkflowRun(
        title="Identity-focused fixture",
        config=RunConfig(
            pipeline_variant=PipelineVariant.SOCIAL_IDENTITY_FOCUSED,
            social_sources=[SocialSource.REDDIT],
            social_identity="night-shift nurses",
            social_identity_type=IdentityType.OCCUPATION,
            social_query="packing tomorrow's lunch after a twelve-hour shift",
            social_candidate_count=1,
        ),
    )


def test_identity_pipeline_is_a_separate_two_stage_variant() -> None:
    """The identity candidate and original social control each expose two comparable stages."""

    definitions = stage_definitions_for(PipelineVariant.SOCIAL_IDENTITY_FOCUSED)

    assert [(definition.number, definition.name) for definition in definitions] == [
        (1, "Identity-Focused Social Behavior to Merchandise Text"),
        (2, "Identity-Focused Social Merchandise Artwork Generation"),
    ]
    assert len(stage_definitions_for(PipelineVariant.SOCIAL_BEHAVIOR_TEXT)) == 2


def test_identity_fixture_preserves_identity_in_copy_and_art_direction() -> None:
    """Fixture output demonstrates the same handoff while making the identity visible."""

    run = _run()
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Identity-Focused Social Behavior to Merchandise Text",
    )
    executor = _executor(Mock())

    input_data = executor.prepare(run, stage)
    result = executor.execute(run, stage, input_data)

    assert result.output_data["candidates"][0]["identity"] == "night-shift nurses"
    assert result.output_data["candidates"][0]["identity_type"] == "occupation"
    assert "night-shift nurses" in result.output_data["candidates"][0]["artwork_text"]


def test_identity_stage_two_carries_identity_into_grok_prompt() -> None:
    """Stage 2 must preserve the Stage 1 identity anchor in the generated image prompt."""

    run = _run()
    stage_repository = Mock()
    stage_one = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Identity-Focused Social Behavior to Merchandise Text",
        output_data=pipeline.execute(
            pipeline.SocialIdentityTextInput(
                sources=[SocialSource.REDDIT],
                identity="night-shift nurses",
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
        stage_name="Identity-Focused Social Merchandise Artwork Generation",
    )
    input_data = executor.prepare(run, stage_two)
    result = executor.execute(run, stage_two, input_data)

    generated_prompt = result.output_data["artworks"][0]["prompt"]
    assert "Target identity: night-shift nurses" in generated_prompt
    assert "identity-specific" in generated_prompt
    assert result.output_data["artworks"][0]["source_url"].startswith("https://fixture.local/")


def test_identity_live_stage_requires_provider_to_preserve_identity() -> None:
    """A live provider that changes the requested identity must fail instead of masking the drift."""

    run = _run()
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Identity-Focused Social Behavior to Merchandise Text",
    )
    candidate = pipeline.SocialIdentityTextCandidate(
        identity="generic healthcare workers",
        identity_type=IdentityType.OCCUPATION,
        identity_evidence="The source discusses a different audience.",
        source_platform=SocialSource.REDDIT,
        source_url="https://reddit.com/r/example/comments/abc/example",
        source_title="Example discussion",
        source_excerpt="A source-backed behavior.",
        audience_context="Generic healthcare workers",
        behavior="Trying to decompress after work.",
        friction_or_pressure="The next shift starts too soon.",
        artwork_text="My lunch break is a clinical trial",
        artwork_prompt="A bold targeted shirt graphic with one identity-specific visual joke.",
        visual_punchline="Lunch becomes a clinical trial.",
        main_visual_metaphor="A lunch container is treated like a lab specimen.",
        audience_specific_cue="A night-shift nurse's documented meal break.",
        tone="dry",
        style_direction="Bold limited-palette screen print.",
        things_to_avoid=["generic healthcare imagery"],
        specificity_reason="The source supports the identity-specific work tension.",
    )
    provider = Mock()
    provider.complete_structured.return_value = SimpleNamespace(
        output=pipeline.SocialIdentityTextOutput(
            candidates=[candidate],
            search_summary="One source-backed behavior.",
        ),
        usage=UsageMetrics(provider="openai", model="gpt-5.6-luna", request_count=1),
    )
    executor = _executor(Mock())
    executor._reasoning_provider = provider

    input_data = executor.prepare(run, stage)

    try:
        executor.execute(run, stage, input_data)
    except ValueError as error:
        assert "changed the target identity" in str(error)
    else:
        raise AssertionError("Provider identity drift should fail the identity-focused stage")
