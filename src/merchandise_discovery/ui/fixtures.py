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


class RunFixture(BaseModel):
    """A complete demo run used to exercise the pipeline layout."""

    run_id: str
    title: str
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

    @property
    def completion_ratio(self) -> float:
        """Return a bounded ratio suitable for Streamlit's progress component."""

        return min(max(self.completed_stages / self.total_stages, 0.0), 1.0)


class RunListItemFixture(BaseModel):
    """Summary data needed by the run listing before live repository reads are connected."""

    run_id: str
    title: str
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
            status=RunStatus.RUNNING,
            progress=35,
            updated="12 minutes ago",
            triggered_by="manual review",
        ),
        RunListItemFixture(
            run_id="016",
            title="Remote workers and decompression rituals",
            status=RunStatus.COMPLETED,
            progress=100,
            updated="2 hours ago",
            triggered_by="manual review",
        ),
        RunListItemFixture(
            run_id="015",
            title="Weekend makers and workshop identity",
            status=RunStatus.COMPLETED,
            progress=100,
            updated="1 day ago",
            triggered_by="scheduled demo",
        ),
        RunListItemFixture(
            run_id="014",
            title="Pet owners after demanding shifts",
            status=RunStatus.FAILED,
            progress=58,
            updated="2 days ago",
            triggered_by="manual review",
        ),
    ]


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
        ("Similarity and IP Check", "Optionally identify duplication and potential IP risks."),
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
        status=RunStatus.RUNNING,
        completed_stages=6,
        estimated_remaining="28 minutes",
        started="12 minutes ago",
        triggered_by="manual review",
        version="v0.1.0",
        current_stage_number=7,
        stages=stages,
    )
