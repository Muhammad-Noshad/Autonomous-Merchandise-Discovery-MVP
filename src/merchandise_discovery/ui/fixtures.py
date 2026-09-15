"""Fixture data used to validate the dashboard before backend integration.

The fixture mirrors the future persisted workflow shape closely enough that UI development does not
invent a second data model. It is deliberately isolated from the production repositories and will
be replaced by application-service calls after the MongoDB chunk is implemented.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.common import RunStatus, StageStatus


class EvidenceFixture(BaseModel):
    """A compact research citation shown in the stage detail panel."""

    title: str
    source: str
    date: str
    excerpt: str


class StageFixture(BaseModel):
    """The UI-facing representation of one pipeline stage."""

    number: int = Field(ge=1, le=17)
    name: str
    summary: str
    status: StageStatus
    duration: str
    progress: int = Field(default=0, ge=0, le=100)
    output_summary: str
    inputs: dict[str, str] = Field(default_factory=dict)
    # Preserve structured snapshots so the UI can explain decisions without flattening every
    # future field into a manually maintained display string.
    input_payload: dict[str, object] = Field(default_factory=dict)
    output_payload: dict[str, object] = Field(default_factory=dict)
    metrics: dict[str, str] = Field(default_factory=dict)
    evidence: list[EvidenceFixture] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    error_message: str | None = None
    logs: list[str] = Field(default_factory=list)


class RunFixture(BaseModel):
    """A complete demo run used to exercise the pipeline layout."""

    run_id: str
    title: str
    selection_seed: int | None = None
    status: RunStatus
    completed_stages: int
    total_stages: int = 17
    estimated_remaining: str
    started: str
    triggered_by: str
    version: str
    current_stage_number: int
    stages: list[StageFixture]
    last_error: str | None = None
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    cost_is_estimate: bool = False

    @property
    def completion_ratio(self) -> float:
        """Return a bounded ratio suitable for Streamlit's progress component."""

        return min(max(self.completed_stages / self.total_stages, 0.0), 1.0)


class RunListItemFixture(BaseModel):
    """Summary data needed by the run listing before live repository reads are connected."""

    run_id: str
    title: str
    selection_seed: int | None = None
    status: RunStatus
    progress: int = Field(ge=0, le=100)
    updated: str
    triggered_by: str


def get_demo_runs() -> list[RunListItemFixture]:
    """Return representative run summaries for the navigation/listing UI."""

    return [
        RunListItemFixture(
            run_id="017",
            title="Autonomous merchandise discovery pipeline",
            selection_seed=17017,
            status=RunStatus.RUNNING,
            progress=35,
            updated="12 minutes ago",
            triggered_by="manual review",
        ),
        RunListItemFixture(
            run_id="016",
            title="Remote workers and decompression rituals",
            selection_seed=16016,
            status=RunStatus.COMPLETED,
            progress=100,
            updated="2 hours ago",
            triggered_by="manual review",
        ),
        RunListItemFixture(
            run_id="015",
            title="Weekend makers and workshop identity",
            selection_seed=15015,
            status=RunStatus.COMPLETED,
            progress=100,
            updated="1 day ago",
            triggered_by="scheduled demo",
        ),
        RunListItemFixture(
            run_id="014",
            title="Pet owners after demanding shifts",
            selection_seed=14014,
            status=RunStatus.FAILED,
            progress=58,
            updated="2 days ago",
            triggered_by="manual review",
        ),
    ]


def _demo_output_payload(number: int, evidence: list[EvidenceFixture]) -> dict[str, object]:
    """Return compact representative output for fixture-mode stage visual validation."""

    seed = {
        "seed_id": "fixture-seed-1",
        "category": "Audience",
        "name": "Pet owners after demanding shifts",
        "metadata": {"priority": 9},
    }
    intersection = {
        "intersection_id": "fixture-intersection-1",
        "identities": ["Pet owners", "Demanding shifts"],
        "coherence_score": 8.6,
        "experience_hypotheses": ["Humor and pets help people decompress after work."],
        "metadata": {"shared_tags": ["decompression", "humor"]},
    }
    niche = {
        "niche_id": "fixture-niche-1",
        "name": "Pet owners + Demanding shifts",
        "evidence_count": 3,
        "opportunity_score": 88,
    }
    concept = {
        "concept_id": "fixture-concept-1",
        "phrase": "Reset Mode",
        "description": "A specific, experience-led phrase about decompressing after demanding shifts.",
        "overall_score": 8.4,
        "selected": True,
        "rank": 1,
    }
    brief = {
        "brief_id": "fixture-brief-1",
        "concept_id": "fixture-concept-1",
        "exact_phrase": "Reset Mode",
        "target_audience": "People sharing the researched experience",
        "main_subject": "A simple symbolic object representing a personal reset ritual",
        "illustration_style": "Clean editorial illustration",
        "composition": "Centered subject with clear negative space",
        "constraints": ["No logos", "Exact phrase spelling", "Legible at merchandise scale"],
    }
    artwork = {
        "artwork_id": "fixture-artwork-1",
        "concept_id": "fixture-concept-1",
        "mime_type": "image/png",
        "width": 1024,
        "height": 1024,
        "file_size_bytes": 128000,
        "source_url": "https://fixture.local/artwork/fixture-concept-1/1.png",
    }
    return {
        1: {"selected_seeds": [seed], "selection_reasons": {"fixture-seed-1": "High priority audience seed."}},
        2: {"identities": [{"value": "Pet owners", "category": "Audience", "dimension_type": "core", "source_seed_name": seed["name"], "affinity_tags": ["pets", "care"]}]},
        3: {"intersections": [intersection]},
        4: {"intersections": [intersection]},
        5: {"accepted": [intersection], "rejected": [{**intersection, "filter_reason": "Rejected as a duplicate identity combination."}]},
        6: {"niches": [niche], "evidence": [item.model_dump() for item in evidence]},
        7: {"signals": [{"niche_id": niche["niche_id"], "confidence": 0.91, "repeated_language": ["specific humor", "decompress after work"], "frustrations": ["Demanding days leave little room to reset."], "rituals": ["Pet-based decompression"], "emotional_signals": ["relief", "belonging"], "experience_summary": "A recognizable decompression ritual creates a strong merchandise opportunity."}]},
        8: {"scores": [{"niche_id": niche["niche_id"], "evidence_strength": 30, "experience_clarity": 25, "audience_fit": 18, "differentiation": 17, "overall_score": 90, "rationale": "Three evidence records and repeated experience signals support the score."}]},
        9: {"concepts": [concept]},
        10: {"evaluations": [{"concept_id": concept["concept_id"], "authenticity": 8.5, "clarity": 8.8, "wearability": 9, "commercial_potential": 8.2, "overall_score": 8.6, "verdict": "keep", "weaknesses": []}]},
        11: {"checks": [{"concept_id": concept["concept_id"], "risk_level": "low", "reason": "No duplicate phrase was found in the current run."}], "survivors": [concept], "rejected": []},
        12: {"finalists": [concept], "rejected": []},
        13: {"briefs": [brief]},
        14: {"prompts": [{"concept_id": concept["concept_id"], "prompt": 'Exact text: "Reset Mode". Clean editorial merchandise artwork, centered subject, readable typography, no logos.'}]},
        15: {"artworks": [artwork]},
        16: {"evaluations": [{"artwork_id": artwork["artwork_id"], "readability": 9, "composition": 9, "quality": 9, "alignment": 9, "decision": "accept", "checks": {"supported_mime_type": True, "minimum_dimensions": True, "square_merchandise_ratio": True}, "issues": []}]},
        17: {"approval_status": "Awaiting human approval", "artworks_ready": 1},
    }.get(number, {})


def get_demo_run() -> RunFixture:
    """Return a representative in-progress run with evidence and artwork metadata."""

    evidence = [
        EvidenceFixture(
            title="Outdoor community discussions",
            source="Public forums",
            date="Apr 24, 2026",
            excerpt="Members repeatedly describe using humor and their pets to decompress after demanding workdays.",
        ),
        EvidenceFixture(
            title="Marketplace language review",
            source="Marketplace listings",
            date="Apr 23, 2026",
            excerpt="Existing products use broad pet-owner language, leaving room for a more specific experience-led phrase.",
        ),
        EvidenceFixture(
            title="Search interest snapshot",
            source="Public search results",
            date="Apr 22, 2026",
            excerpt="Related terms show sustained interest across multiple independent communities.",
        ),
    ]

    stage_definitions = [
        ("Autonomous Seed Discovery", "Select broad identity groups worth investigating."),
        ("Identity Universe Expansion", "Expand each seed into relevant identity dimensions."),
        ("Intersection Generation", "Generate combinations that are likely to coexist naturally."),
        ("Coherence and Experience Hypothesis", "Predict recognizable experiences before research."),
        ("Pre-Research Filter", "Remove duplicates and weak candidates deterministically."),
        ("Niche Research and Validation", "Gather evidence from real public communities."),
        ("Experience Mining", "Extract recurring language, frustrations, and emotional signals."),
        ("Niche Opportunity Scoring", "Combine evidence and qualitative opportunity signals."),
        ("Merchandise Concept Generation", "Turn validated experiences into merchandise concepts."),
        ("Single-Call Concept Critique", "Evaluate authenticity, wearability, and commercial appeal."),
        ("Duplicate Phrase Screen", "Optionally identify duplicate merchandise phrases within this run."),
        ("Final Concept Selection", "Rank surviving concepts and select finalists."),
        ("Structured Design Brief", "Convert each finalist into a visual design brief."),
        ("Grok Prompt Compilation", "Apply consistent merchandise prompt constraints."),
        ("Merchandise Artwork Generation", "Generate a small number of artwork candidates."),
        ("Single-Call Artwork Critique", "Check readability, composition, and concept alignment."),
        ("Human Approval", "Record final approval, rejection, or adjustment decisions."),
    ]

    stages: list[StageFixture] = []
    for number, (name, summary) in enumerate(stage_definitions, start=1):
        if number <= 6:
            status = StageStatus.COMPLETED
            duration = ["42s", "1m 12s", "58s", "1m 6s", "37s", "2m 14s"][number - 1]
            progress = 100
        elif number == 7:
            status = StageStatus.RUNNING
            duration = "1m 9s"
            progress = 64
        elif number == 11:
            status = StageStatus.SKIPPED
            duration = "Optional"
            progress = 0
        else:
            status = StageStatus.PENDING
            duration = "Queued"
            progress = 0

        stages.append(
            StageFixture(
                number=number,
                name=name,
                summary=summary,
                status=status,
                duration=duration,
                progress=progress,
                output_summary=(
                    "The audience repeatedly describes pet-based decompression after demanding shifts, "
                    "with a strong opportunity for specific, experience-led humor."
                    if number == 7
                    else "Stage output will appear here after this stage executes."
                ),
                inputs={
                    "Run": "#017",
                    "Source context": "Prior stage output",
                    "Execution mode": "MVP fixture",
                },
                output_payload=_demo_output_payload(number, evidence),
                metrics=(
                    {
                        "Evidence sources": "3",
                        "Experience signals": "8",
                        "Audience fit": "91 / 100",
                    }
                    if number == 7
                    else {}
                ),
                evidence=evidence if number == 7 else [],
                artifacts=(
                    ["experience-summary.json", "research-citations.json"] if number == 7 else []
                ),
            )
        )

    return RunFixture(
        run_id="017",
        title="Autonomous merchandise discovery pipeline",
        selection_seed=17017,
        status=RunStatus.RUNNING,
        completed_stages=6,
        estimated_remaining="28 minutes",
        started="12 minutes ago",
        triggered_by="manual review",
        version="v0.1.0",
        current_stage_number=7,
        stages=stages,
    )
