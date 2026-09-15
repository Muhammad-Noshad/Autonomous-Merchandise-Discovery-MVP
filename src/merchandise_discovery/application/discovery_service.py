"""Application service for starting and inspecting discovery runs.

This layer coordinates use cases; it should not contain Streamlit rendering or raw MongoDB query
syntax. Those concerns remain behind the entrypoint and repository boundaries.
"""

from dataclasses import dataclass, field
from uuid import uuid4

from merchandise_discovery.domain.models.artifacts import (
    Artwork,
    IdentityIntersection,
    MerchandiseConcept,
    Niche,
)
from merchandise_discovery.domain.models.common import RunStatus
from merchandise_discovery.domain.models.workflow import (
    RunConfig,
    StageExecution,
    StageLog,
    WorkflowRun,
)
from merchandise_discovery.domain.stages.registry import STAGE_DEFINITIONS
from merchandise_discovery.infrastructure.mongo.repositories.artwork_repository import (
    ArtworkRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.brief_repository import (
    BriefRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.concept_repository import (
    ConceptRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.evidence_repository import (
    EvidenceRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.intersection_repository import (
    IntersectionRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.niche_repository import NicheRepository
from merchandise_discovery.infrastructure.mongo.repositories.review_repository import (
    ReviewRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.run_repository import RunRepository
from merchandise_discovery.infrastructure.mongo.repositories.stage_execution_repository import (
    StageExecutionRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.stage_log_repository import (
    StageLogRepository,
)


@dataclass(frozen=True)
class RunSnapshot:
    """A run aggregate plus its stage attempts, assembled for application callers."""

    run: WorkflowRun
    stages: list[StageExecution]
    logs: list[StageLog] = field(default_factory=list)


@dataclass(frozen=True)
class RunDeletionSummary:
    """Counts removed by the explicit run cleanup use case."""

    run_id: str
    deleted_counts: dict[str, int]

    @property
    def total_deleted(self) -> int:
        """Return the number of MongoDB documents removed across the cascade."""

        return sum(self.deleted_counts.values())


class DiscoveryService:
    """Coordinate run creation without exposing MongoDB or Streamlit to callers."""

    def __init__(
        self,
        run_repository: RunRepository,
        stage_repository: StageExecutionRepository,
        intersection_repository: IntersectionRepository | None = None,
        concept_repository: ConceptRepository | None = None,
        artwork_repository: ArtworkRepository | None = None,
        stage_log_repository: StageLogRepository | None = None,
        niche_repository: NicheRepository | None = None,
        *,
        evidence_repository: EvidenceRepository | None = None,
        brief_repository: BriefRepository | None = None,
        review_repository: ReviewRepository | None = None,
    ):
        self._runs = run_repository
        self._stages = stage_repository
        self._intersections = intersection_repository
        self._concepts = concept_repository
        self._artworks = artwork_repository
        self._stage_logs = stage_log_repository
        self._niches = niche_repository
        self._evidence = evidence_repository
        self._briefs = brief_repository
        self._reviews = review_repository

    def create_run(
        self,
        title: str,
        *,
        config: RunConfig | None = None,
        triggered_by: str = "manual",
    ) -> WorkflowRun:
        """Create a run and initialize its stage records from the stable stage registry."""

        run = WorkflowRun(
            title=title,
            config=config or RunConfig(),
            total_stages=len(STAGE_DEFINITIONS),
            triggered_by=triggered_by,
        )
        self._runs.create(run)
        self._stages.create_for_run(
            run.run_id,
            [
                (definition.number, definition.name, definition.optional, definition.version)
                for definition in STAGE_DEFINITIONS
            ],
            enable_optional=run.config.enable_similarity_ip_check,
        )
        return run

    def get_run(self, run_id: str) -> WorkflowRun | None:
        """Return the persisted run state for dashboard reads."""

        return self._runs.get_by_id(run_id)

    def list_runs(self, limit: int = 50) -> list[WorkflowRun]:
        """Return bounded run history without exposing repository details to the UI."""

        return self._runs.list_recent(limit)

    def delete_run(self, run_id: str) -> RunDeletionSummary:
        """Delete one run and every run-owned record through repository-owned cascade queries.

        The action is available for every run status. The run is first marked cancelled using its
        optimistic-lock version; this closes the worker's future claim path before child records are
        removed. An already-running stage may still finish its current operation and will fail its
        subsequent run-state update, so deletion remains an explicitly destructive action.
        """

        run = self._runs.get_by_id(run_id)
        if run is None:
            raise ValueError(f"Run not found: {run_id}")

        repositories = {
            "stage_executions": self._stages,
            "stage_logs": self._stage_logs,
            "intersections": self._intersections,
            "niches": self._niches,
            "evidence": self._evidence,
            "concepts": self._concepts,
            "briefs": self._briefs,
            "artworks": self._artworks,
            "reviews": self._reviews,
        }
        missing = [name for name, repository in repositories.items() if repository is None]
        if missing:
            raise RuntimeError(
                "Run deletion is not fully configured; missing repositories: " + ", ".join(missing)
            )

        # Marking the aggregate cancelled first prevents a pending/failed run from being claimed by
        # the worker while its dependent records are being removed. A changed version aborts safely.
        self._runs.update_status(
            run_id,
            expected_version=run.version,
            status=RunStatus.CANCELLED,
            current_stage_number=run.current_stage_number,
        )

        deleted_counts = {
            name: repository.delete_for_run(run_id)
            for name, repository in repositories.items()
        }
        deleted_counts["runs"] = self._runs.delete_by_id(run_id)
        if deleted_counts["runs"] != 1:
            raise RuntimeError(f"Run cleanup could not remove the run record: {run_id}")
        return RunDeletionSummary(run_id=run_id, deleted_counts=deleted_counts)

    def get_run_snapshot(self, run_id: str) -> RunSnapshot | None:
        """Load one run and all its stage attempts as a consistent application-level view."""

        run = self._runs.get_by_id(run_id)
        if run is None:
            return None
        logs = self._stage_logs.list_for_run(run_id) if self._stage_logs else []
        return RunSnapshot(run=run, stages=self._stages.list_for_run(run_id), logs=logs)

    def list_intersections(self, run_id: str) -> list[IdentityIntersection]:
        """Return persisted discovery candidates without exposing the repository to the UI."""

        if self._intersections is None:
            return []
        return self._intersections.list_for_run(run_id)

    def list_concepts(self, run_id: str) -> list[MerchandiseConcept]:
        """Return persisted concepts for the live concepts page."""

        if self._concepts is None:
            return []
        return self._concepts.list_for_run(run_id)

    def list_artworks(self, run_id: str) -> list[Artwork]:
        """Return persisted artwork candidates for the review page."""

        if self._artworks is None:
            return []
        return self._artworks.list_for_run(run_id)

    def list_niches(self, run_id: str) -> list[Niche]:
        """Return the persisted niches belonging to one run."""

        if self._niches is None:
            return []
        return self._niches.list_for_run(run_id)

    def create_manual_niche(
        self,
        run_id: str,
        *,
        name: str,
        experience_summary: str,
        coherence_score: float,
        opportunity_score: float,
    ) -> Niche:
        """Create a manual niche through the repository boundary for an existing run."""

        if self._niches is None:
            raise RuntimeError("Niche persistence is not configured.")
        if self._runs.get_by_id(run_id) is None:
            raise ValueError(f"Cannot create a niche for unknown run: {run_id}")
        niche = Niche(
            run_id=run_id,
            intersection_id=f"manual-{uuid4()}",
            name=name.strip(),
            experience_summary=experience_summary.strip() or None,
            coherence_score=coherence_score,
            opportunity_score=opportunity_score,
        )
        return self._niches.save(niche)
