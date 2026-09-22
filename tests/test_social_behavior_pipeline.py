"""Tests for the one-stage social behavior to text pipeline."""

from types import SimpleNamespace
from unittest.mock import Mock

from merchandise_discovery.application.discovery_stage_executor import DiscoveryStageExecutor
from merchandise_discovery.domain.models.common import PipelineVariant, SocialSource
from merchandise_discovery.domain.models.usage import UsageMetrics
from merchandise_discovery.domain.models.workflow import RunConfig, StageExecution, WorkflowRun
from merchandise_discovery.domain.pipelines.social_behavior_text import pipeline
from merchandise_discovery.domain.stages.registry import stage_definitions_for


def _executor(stage_repository: Mock) -> DiscoveryStageExecutor:
    """Construct the executor with repository doubles; the social stage needs none of them."""

    return DiscoveryStageExecutor(
        *(Mock() for _ in range(2)),
        stage_repository,
        *(Mock() for _ in range(7)),
    )


def test_social_behavior_pipeline_has_one_stage() -> None:
    """The experimental pipeline does not initialize the legacy discovery funnel."""

    definitions = stage_definitions_for(PipelineVariant.SOCIAL_BEHAVIOR_TEXT)

    assert [(definition.number, definition.name) for definition in definitions] == [
        (1, "Social Behavior to Merchandise Text")
    ]


def test_social_behavior_pipeline_fixture_returns_text_candidates() -> None:
    """Fixture mode keeps the new UI demonstrable without pretending a social search occurred."""

    run = WorkflowRun(
        title="Social behavior fixture",
        config=RunConfig(
            pipeline_variant=PipelineVariant.SOCIAL_BEHAVIOR_TEXT,
            social_sources=[SocialSource.REDDIT],
            social_query="people optimizing sleep after doom-scrolling",
            social_candidate_count=2,
        ),
    )
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Social Behavior to Merchandise Text",
    )
    executor = _executor(Mock())

    input_data = executor.prepare(run, stage)
    result = executor.execute(run, stage, input_data)

    assert len(result.output_data["candidates"]) == 2
    assert result.output_data["model"] == "deterministic"
    assert result.output_data["candidates"][0]["source_platform"] == SocialSource.REDDIT.value


def test_social_behavior_pipeline_passes_live_source_scope_to_provider() -> None:
    """Live execution makes one structured request constrained to the selected social domains."""

    run = WorkflowRun(
        title="Social behavior live",
        config=RunConfig(
            pipeline_variant=PipelineVariant.SOCIAL_BEHAVIOR_TEXT,
            social_sources=[SocialSource.REDDIT, SocialSource.X],
            social_query="night workers trying to stay sane",
            social_candidate_count=1,
        ),
    )
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Social Behavior to Merchandise Text",
    )
    candidate = pipeline.SocialBehaviorTextCandidate(
        source_platform=SocialSource.REDDIT,
        source_url="https://reddit.com/r/example/comments/abc/example",
        source_title="Example discussion",
        source_excerpt="A source-backed behavior.",
        audience_context="Night workers",
        behavior="Trying to decompress after a shift.",
        friction_or_pressure="The next shift starts too soon.",
        artwork_text="My sleep schedule is a group project",
        specificity_reason="The line reflects a recognizable shift-work tension.",
    )
    provider = Mock()
    provider.complete_structured.return_value = SimpleNamespace(
        output=pipeline.SocialBehaviorTextOutput(
            candidates=[candidate],
            search_summary="One source-backed behavior.",
        ),
        usage=UsageMetrics(provider="openai", model="gpt-4o-mini", request_count=1),
    )
    executor = _executor(Mock())
    executor._reasoning_provider = provider

    input_data = executor.prepare(run, stage)
    result = executor.execute(run, stage, input_data)

    provider.complete_structured.assert_called_once()
    call = provider.complete_structured.call_args.kwargs
    assert call["web_search_domains"] == ("reddit.com", "x.com")
    assert result.output_data["candidates"][0]["artwork_text"] == (
        "My sleep schedule is a group project"
    )


def test_social_behavior_prompt_requires_standalone_personal_copy() -> None:
    """The product line must carry enough context without relying on hidden metadata."""

    instructions = pipeline.reasoning_instructions()

    assert "MUST make sense when read alone" in instructions
    assert "Preserve the personal relationship" in instructions
    assert "style of a targeted T-shirt" in instructions
    assert "there is no hard length limit" in instructions
    assert "self-contained mini-story" in instructions
    assert "who or what situation this is about" in instructions
    assert "Do not compress the idea into a vague aphorism" in instructions
    assert "one dominant scene or behavior" in instructions
    assert "Remove source-detail lists" in instructions
    assert "Avoid generic achievement statements" in instructions
