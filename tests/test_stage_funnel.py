"""Tests for the deterministic Stage 1–5 discovery funnel."""

import pytest

from merchandise_discovery.domain.models.artifacts import IdentityIntersection
from merchandise_discovery.domain.stages.stage_01_seed_discovery import (
    SeedDiscoveryInput,
    select_candidate_seeds,
)
from merchandise_discovery.domain.stages.stage_01_seed_discovery import (
    execute as execute_seed_discovery,
)
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
)
from merchandise_discovery.domain.stages.stage_03_intersection_generation import (
    execute as execute_intersection_generation,
)
from merchandise_discovery.domain.stages.stage_04_coherence_hypothesis import (
    CoherenceInput,
    ResearchSelection,
    Stage4ReasoningOutput,
    reasoning_instructions,
)
from merchandise_discovery.domain.stages.stage_04_coherence_hypothesis import (
    execute as execute_coherence,
)
from merchandise_discovery.domain.stages.stage_05_pre_research_filter import (
    PreResearchFilterInput,
)
from merchandise_discovery.domain.stages.stage_05_pre_research_filter import (
    execute as execute_pre_research_filter,
)
from merchandise_discovery.shared.seed_loader import load_seed_fixture


def test_discovery_funnel_produces_bounded_inspectable_results() -> None:
    """The first five stages produce accepted and rejected candidates deterministically."""

    seeds = load_seed_fixture()
    selected = execute_seed_discovery(SeedDiscoveryInput(max_seed_items=12), seeds)
    expanded = execute_identity_expansion(
        IdentityExpansionInput(selected_seeds=selected.selected_seeds)
    )
    candidates = execute_intersection_generation(
        IntersectionGenerationInput(identities=expanded.identities, max_intersections=10),
        run_id="run-test",
    )
    scored = execute_coherence(CoherenceInput(intersections=candidates.intersections))
    filtered = execute_pre_research_filter(
        PreResearchFilterInput(intersections=scored.intersections, max_intersections=10)
    )

    assert len(selected.selected_seeds) == 12
    expected_identity_count = sum(
        1 + len(seed.metadata.get("dimensions", [])) for seed in selected.selected_seeds
    )
    assert len(expanded.identities) == expected_identity_count
    assert len(candidates.intersections) == 30
    assert len(filtered.accepted) <= 10
    assert len(filtered.accepted) + len(filtered.rejected) == 30
    assert all(item.eligible_for_research for item in filtered.accepted)
    assert all(item.filter_reason for item in filtered.rejected)


def test_stage_04_provider_contract_selects_a_diverse_hopeful_portfolio() -> None:
    """Stage 4 asks AI to avoid several individually strong versions of one opportunity theme."""

    instructions = reasoning_instructions()

    assert "one research portfolio" in instructions
    assert "prefer candidates that differ in primary audience" in instructions
    assert "hopeful opportunities" in instructions
    assert "recent-relocator candidates" in instructions
    assert "distinct portfolio angle" in instructions


def test_pre_research_filter_does_not_reapply_deduplication() -> None:
    """Stage 5 preserves the explicit Stage 4 selection instead of making a new decision."""

    first = IdentityIntersection(
        run_id="run-test",
        identities=["Remote workers", "Home gardeners"],
        coherence_score=8,
        experience_hypotheses=["A useful hypothesis."],
    )
    duplicate = IdentityIntersection(
        run_id="run-test",
        identities=["Home gardeners", "Remote workers"],
        coherence_score=7,
        experience_hypotheses=["A duplicate hypothesis."],
    )

    result = execute_pre_research_filter(
        PreResearchFilterInput(
            intersections=[duplicate, first],
            selected_intersection_ids=[duplicate.intersection_id, first.intersection_id],
        )
    )

    assert len(result.accepted) == 2
    assert not result.rejected


def test_stage_04_merges_structured_provider_evaluation() -> None:
    """Stage 4 maps the typed AI selection response onto trusted intersections."""

    intersection = IdentityIntersection(
        intersection_id="intersection-1",
        run_id="run-test",
        identities=["Night-shift nurses", "Coffee rituals", "Practical values"],
        metadata={"shared_tags": ["ritual", "decompression"]},
    )
    reasoning = Stage4ReasoningOutput(
        selections=[
            ResearchSelection(
                intersection_id=intersection.intersection_id,
                coherence_score=8.4,
                research_value_score=9.1,
                confidence=0.91,
                selection_reason=(
                    "The coffee ritual and practical values express a recognizable decompression "
                    "experience for night-shift nurses."
                ),
            )
        ],
        summary="The candidate is coherent and valuable to research.",
    )

    result = execute_coherence(
        CoherenceInput(intersections=[intersection]),
        reasoning_output=reasoning,
        model="gpt-4o-mini",
    )

    enriched = result.intersections[0]
    assert result.provider_selections_count == 1
    assert result.model == "gpt-4o-mini"
    assert enriched.coherence_score == 8.4
    assert enriched.experience_hypotheses == [reasoning.selections[0].selection_reason]
    assert enriched.metadata["selection_reason"] == reasoning.selections[0].selection_reason
    assert enriched.metadata["research_value_score"] == 9.1
    assert enriched.metadata["coherence_generation_method"] == "provider"


def test_stage_04_requires_the_configured_research_count() -> None:
    """AI cannot silently under-select when enough valid candidates are available."""

    intersections = [
        IdentityIntersection(
            intersection_id=f"intersection-{index}",
            run_id="run-test",
            identities=["Night-shift nurses", f"Coffee ritual {index}"],
        )
        for index in range(2)
    ]
    reasoning = Stage4ReasoningOutput(
        selections=[
            ResearchSelection(
                intersection_id=intersections[0].intersection_id,
                selection_reason="The first candidate expresses a concrete repeated ritual.",
                coherence_score=8,
                research_value_score=8,
                confidence=0.9,
            )
        ],
        summary="One candidate selected.",
    )

    with pytest.raises(ValueError, match="exactly the configured research count"):
        execute_coherence(
            CoherenceInput(intersections=intersections, max_researched_niches=2),
            reasoning_output=reasoning,
            model="gpt-4o-mini",
        )


def test_pre_research_filter_passes_through_stage_4_selection() -> None:
    """Stage 5 preserves Stage 4's decision and no longer applies a second filter."""

    selected = IdentityIntersection(
        intersection_id="selected",
        run_id="run-test",
        identities=["Night-shift nurses", "Coffee rituals"],
        eligible_for_research=True,
        filter_reason=None,
    )
    not_selected = IdentityIntersection(
        intersection_id="not-selected",
        run_id="run-test",
        identities=["Remote workers", "Home gardeners"],
        filter_reason="Not selected by AI for the configured research budget.",
    )

    result = execute_pre_research_filter(
        PreResearchFilterInput(
            intersections=[selected, not_selected],
            selected_intersection_ids=["selected"],
        )
    )

    assert [item.intersection_id for item in result.accepted] == ["selected"]
    assert [item.intersection_id for item in result.rejected] == ["not-selected"]
    assert len(result.all_intersections) == 2


def test_stage_01_seed_discovery_with_reasoning_output() -> None:
    """Stage 1 attaches provider reasoning to the reproducibly selected sample."""
    from merchandise_discovery.domain.stages.stage_01_seed_discovery import (
        SeedAnalysis,
        Stage1ReasoningOutput,
    )

    seeds = load_seed_fixture()
    input_data = SeedDiscoveryInput(max_seed_items=4, selection_seed=21)
    selected = select_candidate_seeds(input_data, seeds)
    selected_seed = selected[0]
    reasoning = Stage1ReasoningOutput(
        executive_summary="High potential seed portfolio.",
        evaluations=[
            SeedAnalysis(
                seed_id=selected_seed.seed_id,
                seed_name=selected_seed.name,
                category=selected_seed.category,
                merchandise_potential="Apparel and mugs.",
                target_audience_appeal="Work-from-home humor.",
                selection_reason="Top priority audience for POD.",
            )
        ],
    )
    result = execute_seed_discovery(
        input_data,
        seeds,
        reasoning_output=reasoning,
        model="gpt-4o-mini",
    )
    assert len(result.selected_seeds) == 4
    assert result.model == "gpt-4o-mini"
    assert result.executive_summary == "High potential seed portfolio."
    assert result.selection_reasons[selected_seed.seed_id] == "Top priority audience for POD."
    assert len(result.evaluations) == 1


def test_stage_01_selection_is_reproducible_and_category_balanced() -> None:
    """One selection seed reproduces the same 4/4/4 sample from the three categories."""

    seeds = load_seed_fixture()
    input_data = SeedDiscoveryInput(max_seed_items=12, selection_seed=12345)

    first = select_candidate_seeds(input_data, seeds)
    second = select_candidate_seeds(input_data, seeds)

    assert [seed.seed_id for seed in first] == [seed.seed_id for seed in second]
    categories = {seed.category for seed in first}
    assert {category.value: sum(seed.category == category for seed in first) for category in categories} == {
        "audience": 4,
        "interest": 4,
        "value": 4,
    }


def test_stage_01_different_selection_seeds_can_explore_different_records() -> None:
    """Changing only the random state can produce a different sample without replacement."""

    seeds = load_seed_fixture()
    first = select_candidate_seeds(SeedDiscoveryInput(max_seed_items=12, selection_seed=1), seeds)
    second = select_candidate_seeds(SeedDiscoveryInput(max_seed_items=12, selection_seed=2), seeds)

    assert [seed.seed_id for seed in first] != [seed.seed_id for seed in second]


def test_stage_02_normalizes_structured_provider_dimensions() -> None:
    """Provider dimensions inherit trusted source metadata and retain quality signals."""

    seed = load_seed_fixture()[0]
    dimensions = [
        GeneratedDimension(
            dimension_type="routine",
            value="working from a home office",
            affinity_tags=["home-office"],
            confidence=0.9,
            merchandise_relevance=8,
            rationale="A repeated routine creates recognizable identity language.",
        ),
        GeneratedDimension(
            dimension_type="tension",
            value="blurred work and personal boundaries",
            affinity_tags=["boundaries"],
            confidence=0.88,
            merchandise_relevance=9,
            rationale="The tension is common and easy to express visually.",
        ),
        GeneratedDimension(
            dimension_type="language",
            value="camera fatigue",
            affinity_tags=["digital-routines"],
            confidence=0.95,
            merchandise_relevance=8,
            rationale="The phrase is concise and recognizable within the group.",
        ),
        GeneratedDimension(
            dimension_type="ritual",
            value="closing the laptop at the end of the day",
            affinity_tags=["work-life-boundaries"],
            confidence=0.91,
            merchandise_relevance=7,
            rationale="A concrete ritual can translate into an experience-led concept.",
        ),
    ]
    provider_output = Stage2ReasoningOutput(
        expansions=[SeedExpansion(source_seed_id=seed.seed_id, dimensions=dimensions)],
        summary="The seed has distinct digital routines and work-life tensions.",
    )

    result = execute_identity_expansion(
        IdentityExpansionInput(selected_seeds=[seed]),
        reasoning_output=provider_output,
        model="gpt-4o-mini",
    )

    generated = [item for item in result.identities if item.provenance == "provider"]
    assert len(generated) == 4
    assert all(item.category == seed.category for item in generated)
    assert all(item.priority == seed.metadata["priority"] for item in generated)
    assert generated[0].confidence == 0.9
    assert result.model == "gpt-4o-mini"
    assert result.summary == provider_output.summary
    assert result.provider_expansions[0]["source_seed_id"] == seed.seed_id
