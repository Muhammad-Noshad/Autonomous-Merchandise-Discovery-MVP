"""Tests for selectable baseline and compact pipeline definitions."""

from unittest.mock import Mock

from merchandise_discovery.application.discovery_service import DiscoveryService, RunSnapshot
from merchandise_discovery.application.discovery_stage_executor import DiscoveryStageExecutor
from merchandise_discovery.domain.models.artifacts import (
    IdentityIntersection,
    Niche,
    ResearchEvidence,
)
from merchandise_discovery.domain.models.common import PipelineVariant
from merchandise_discovery.domain.models.workflow import RunConfig, StageExecution, WorkflowRun
from merchandise_discovery.domain.stages.registry import stage_definitions_for
from merchandise_discovery.domain.stages.stage_06_compact_research_development import (
    CompactDevelopmentInput,
    build_reasoning_prompt,
    reasoning_instructions,
)
from merchandise_discovery.domain.stages.stage_06_compact_research_development import (
    execute as execute_compact_stage,
)
from merchandise_discovery.infrastructure.providers.research_provider import (
    FixtureResearchProvider,
)
from merchandise_discovery.ui.adapters import snapshot_to_fixture


def _intersection() -> IdentityIntersection:
    """Return one Stage 5-selected candidate suitable for a compact fixture run."""

    return IdentityIntersection(
        intersection_id="intersection-1",
        run_id="run-test",
        identities=["Night-shift nurses", "Coffee rituals"],
        experience_hypotheses=["A repeatable decompression ritual after demanding shifts."],
        coherence_score=8.5,
        eligible_for_research=True,
    )


def test_compact_registry_contains_only_its_executed_stages() -> None:
    """Compact runs omit the merged Stage 5 while preserving downstream stage numbers."""

    definitions = stage_definitions_for(PipelineVariant.COMPACT_RESEARCH_FIRST)

    assert len(definitions) == 8
    assert [definition.number for definition in definitions] == [1, 2, 3, 4, 6, 7, 8, 9]
    assert definitions[4].name == "AI Merchandise Development"
    assert definitions[7].name == "Artwork Results"
    assert len(stage_definitions_for(PipelineVariant.BASELINE)) == 17


def test_compact_stage_produces_research_and_concepts() -> None:
    """The compact stage persists the same evidence and concept outputs needed downstream."""

    result = execute_compact_stage(
        CompactDevelopmentInput(
            intersections=[_intersection()],
            max_researched_niches=1,
            concepts_per_niche=2,
        ),
        research_provider=FixtureResearchProvider(),
        reasoning_provider=None,
        run_id="run-test",
    )

    assert len(result.niches) == 1
    assert len(result.evidence) == 3
    assert len(result.signals) == 1
    assert len(result.concepts) == 2
    assert len(result.briefs) == 2
    assert len(result.prompts) == 2
    assert result.model == "deterministic"
    assert all(
        prompt.combination_name == "Night-shift nurses + Coffee rituals"
        for prompt in result.prompts
    )


def test_compact_reasoning_prompt_isolates_evidence_by_niche() -> None:
    """The provider receives an explicit evidence allow-list for every niche block."""

    first = Niche(
        run_id="run-test",
        intersection_id="intersection-1",
        name="Night-shift nurses",
        coherence_score=8.5,
        evidence_count=1,
        validated=True,
    )
    second = first.model_copy(
        update={"niche_id": "niche-2", "intersection_id": "intersection-2", "name": "Remote gardeners"}
    )
    first_evidence = ResearchEvidence(
        run_id="run-test",
        niche_id=first.niche_id,
        url="https://example.com/first",
        title="First niche source",
        source="Example",
        excerpt="A first niche observation.",
    )
    second_evidence = ResearchEvidence(
        run_id="run-test",
        niche_id=second.niche_id,
        url="https://example.com/second",
        title="Second niche source",
        source="Example",
        excerpt="A second niche observation.",
    )

    prompt = build_reasoning_prompt([first, second], [first_evidence, second_evidence])

    assert f'"allowed_evidence_ids": ["{first_evidence.evidence_id}"]' in prompt
    assert f'"allowed_evidence_ids": ["{second_evidence.evidence_id}"]' in prompt
    assert "never cite an ID from another block" in prompt


def test_compact_reasoning_contract_requires_audience_recognition_copy() -> None:
    """Compact concepts must use lived-experience copy instead of generic merchandise titles."""

    instructions = reasoning_instructions()

    assert "That is literally me" in instructions
    assert "first-person, second-person, a shared observation" in instructions
    assert "Do not force a grammatical template" in instructions
    assert "do not begin every concept with 'I'" in instructions
    assert "I Garden Between Naps" not in instructions
    assert "product category, club name, campaign title" in instructions


def test_create_run_passes_selected_pipeline_variant_to_stage_setup() -> None:
    """The application service owns variant persistence and stage-slot initialization."""

    run_repository = Mock()
    stage_repository = Mock()
    service = DiscoveryService(run_repository, stage_repository)

    run = service.create_run(
        "Compact test",
        config=RunConfig(pipeline_variant=PipelineVariant.COMPACT_RESEARCH_FIRST),
    )

    assert run.config.pipeline_variant == PipelineVariant.COMPACT_RESEARCH_FIRST
    assert "disabled_stage_numbers" not in stage_repository.create_for_run.call_args.kwargs


def test_compact_stage_7_preparation_reads_stage_6_prompts() -> None:
    """Compact artwork generation consumes prompts emitted directly by Stage 6."""

    compact_output = execute_compact_stage(
        CompactDevelopmentInput(
            intersections=[_intersection()],
            max_researched_niches=1,
            concepts_per_niche=1,
        ),
        research_provider=FixtureResearchProvider(),
        reasoning_provider=None,
        run_id="run-test",
    )
    stage_repository = Mock()
    stage_repository.get_latest.side_effect = [
        StageExecution(
            run_id="run-test",
            stage_number=6,
            stage_name="AI Merchandise Development",
            output_data=compact_output.model_dump(mode="python"),
        ),
    ]
    executor = DiscoveryStageExecutor(
        *(Mock() for _ in range(2)),
        stage_repository,
        *(Mock() for _ in range(7)),
    )
    run = WorkflowRun(
        title="Compact preparation",
        config=RunConfig(pipeline_variant=PipelineVariant.COMPACT_RESEARCH_FIRST),
    )

    prepared = executor.prepare(
        run,
        StageExecution(run_id=run.run_id, stage_number=7, stage_name="Merchandise Artwork Generation"),
    )

    assert len(prepared["prompts"]) == 1
    assert stage_repository.get_latest.call_args_list[0].args == (run.run_id, 6)


def test_compact_detail_view_hides_folded_stages() -> None:
    """Compact detail pages show only active stages while retaining accurate progress totals."""

    run = WorkflowRun(
        title="Compact detail",
        config=RunConfig(pipeline_variant=PipelineVariant.COMPACT_RESEARCH_FIRST),
        completed_stages=6,
    )
    stages = [
        StageExecution(run_id=run.run_id, stage_number=number, stage_name=f"Stage {number}")
        for number in range(1, 18)
    ]

    fixture = snapshot_to_fixture(RunSnapshot(run=run, stages=stages))

    assert [stage.number for stage in fixture.stages] == [1, 2, 3, 4, 6, 7, 8, 9]
    assert fixture.total_stages == 8
    assert fixture.completed_stages == 6
    assert fixture.stages[7].name == "Artwork Results"
    assert fixture.stages[4].summary == (
        "Search the selected niches, synthesize evidence, and generate concepts, briefs, and artwork prompts."
    )
    assert fixture.stages[5].summary == "Generate artwork candidates from compact-stage prompts."
    assert fixture.stages[6].summary == "Run deterministic artwork quality checks."
    assert fixture.stages[7].summary == "Display all generated artwork candidates for visual review."
