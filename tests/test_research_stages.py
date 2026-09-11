"""Tests for the local, evidence-linked research and opportunity stages."""

from merchandise_discovery.domain.models.artifacts import IdentityIntersection
from merchandise_discovery.domain.stages.stage_06_niche_research import NicheResearchInput
from merchandise_discovery.domain.stages.stage_06_niche_research import (
    execute as execute_research,
)
from merchandise_discovery.domain.stages.stage_07_experience_mining import ExperienceMiningInput
from merchandise_discovery.domain.stages.stage_07_experience_mining import (
    execute as execute_mining,
)
from merchandise_discovery.domain.stages.stage_08_opportunity_scoring import OpportunityScoreInput
from merchandise_discovery.domain.stages.stage_08_opportunity_scoring import (
    execute as execute_scoring,
)
from merchandise_discovery.infrastructure.providers.research_provider import FixtureResearchProvider


def test_research_stage_bounds_targets_and_preserves_provenance() -> None:
    """Only eligible targets enter research, and every returned record has source ownership."""

    intersections = [
        IdentityIntersection(
            intersection_id="intersection-1",
            run_id="run-test",
            identities=["Remote workers", "Home gardeners"],
            experience_hypotheses=["They use small rituals to reset after work."],
            coherence_score=8.5,
            eligible_for_research=True,
        ),
        IdentityIntersection(
            intersection_id="intersection-2",
            run_id="run-test",
            identities=["Pet owners", "Night-shift workers"],
            coherence_score=9.0,
            eligible_for_research=False,
        ),
    ]

    result = execute_research(
        NicheResearchInput(intersections=intersections, max_researched_niches=1),
        FixtureResearchProvider(),
        run_id="run-test",
    )

    assert len(result.niches) == 1
    assert result.selected_intersection_ids == ["intersection-1"]
    assert len(result.evidence) == 3
    assert all(item.run_id == "run-test" for item in result.evidence)
    assert all(item.niche_id == result.niches[0].niche_id for item in result.evidence)


def test_experience_mining_keeps_evidence_lineage() -> None:
    """Recurring signals must point back to the exact evidence records that triggered them."""

    research = execute_research(
        NicheResearchInput(
            intersections=[
                IdentityIntersection(
                    intersection_id="intersection-1",
                    run_id="run-test",
                    identities=["Remote workers", "Home gardeners"],
                    coherence_score=8.5,
                    eligible_for_research=True,
                )
            ],
            max_researched_niches=1,
        ),
        FixtureResearchProvider(),
        run_id="run-test",
    )

    mined = execute_mining(
        ExperienceMiningInput(niches=research.niches, evidence=research.evidence)
    )

    assert len(mined.signals) == 1
    assert mined.signals[0].confidence == 1
    assert set(mined.signals[0].evidence_ids) == {
        evidence.evidence_id for evidence in research.evidence
    }
    assert mined.signals[0].experience_summary


def test_opportunity_scoring_is_bounded_and_reproducible() -> None:
    """The same stored niche and signals produce the same score and rationale."""

    research = execute_research(
        NicheResearchInput(
            intersections=[
                IdentityIntersection(
                    intersection_id="intersection-1",
                    run_id="run-test",
                    identities=["Remote workers", "Home gardeners"],
                    coherence_score=8.5,
                    eligible_for_research=True,
                )
            ],
            max_researched_niches=1,
        ),
        FixtureResearchProvider(),
        run_id="run-test",
    )
    mined = execute_mining(
        ExperienceMiningInput(niches=research.niches, evidence=research.evidence)
    )
    input_data = OpportunityScoreInput(niches=research.niches, signals=mined.signals)

    first = execute_scoring(input_data)
    second = execute_scoring(input_data)

    assert first.scores[0].overall_score == second.scores[0].overall_score
    assert 0 <= first.scores[0].overall_score <= 100
    assert first.niches[0].opportunity_score == first.scores[0].overall_score
    assert first.niches[0].validated is True
