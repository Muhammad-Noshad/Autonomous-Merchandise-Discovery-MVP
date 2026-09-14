"""Tests for the deterministic Stage 1–5 discovery funnel."""

from merchandise_discovery.domain.models.artifacts import IdentityIntersection
from merchandise_discovery.domain.stages.stage_01_seed_discovery import (
    SeedDiscoveryInput,
)
from merchandise_discovery.domain.stages.stage_01_seed_discovery import (
    execute as execute_seed_discovery,
)
from merchandise_discovery.domain.stages.stage_02_identity_expansion import (
    IdentityExpansionInput,
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


def test_pre_research_filter_rejects_reordered_duplicates() -> None:
    """Canonical identity ordering prevents the same combination entering research twice."""

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
        PreResearchFilterInput(intersections=[duplicate, first], max_intersections=10)
    )

    assert len(result.accepted) == 1
    assert len(result.rejected) == 1
    assert result.rejected[0].filter_reason == "Rejected as a duplicate identity combination."


def test_stage_01_seed_discovery_with_reasoning_output() -> None:
    """Stage 1 integrates structured reasoning evaluations while preserving deterministic ordering."""
    from merchandise_discovery.domain.stages.stage_01_seed_discovery import (
        SeedAnalysis,
        Stage1ReasoningOutput,
    )

    seeds = load_seed_fixture()
    reasoning = Stage1ReasoningOutput(
        executive_summary="High potential seed portfolio.",
        evaluations=[
            SeedAnalysis(
                seed_id=seeds[0].seed_id,
                seed_name=seeds[0].name,
                category=seeds[0].category,
                merchandise_potential="Apparel and mugs.",
                target_audience_appeal="Work-from-home humor.",
                selection_reason="Top priority audience for POD.",
            )
        ],
    )
    result = execute_seed_discovery(
        SeedDiscoveryInput(max_seed_items=4),
        seeds,
        reasoning_output=reasoning,
        model="gpt-4o-mini",
    )
    assert len(result.selected_seeds) == 4
    assert result.model == "gpt-4o-mini"
    assert result.executive_summary == "High potential seed portfolio."
    assert result.selection_reasons[seeds[0].seed_id] == "Top priority audience for POD."
    assert len(result.evaluations) == 1
