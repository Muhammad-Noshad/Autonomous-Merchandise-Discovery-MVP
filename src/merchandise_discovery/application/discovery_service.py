"""Application service for starting and inspecting discovery runs.

This layer coordinates use cases; it should not contain Streamlit rendering or raw MongoDB query
syntax. Those concerns remain behind the entrypoint and repository boundaries.
"""

from dataclasses import dataclass, field

from merchandise_discovery.domain.models.artifacts import (
    Artwork,
    IdentityIntersection,
    MerchandiseConcept,
)
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
from merchandise_discovery.infrastructure.mongo.repositories.concept_repository import (
    ConceptRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.intersection_repository import (
    IntersectionRepository,
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
    ):
        self._runs = run_repository
        self._stages = stage_repository
        self._intersections = intersection_repository
        self._concepts = concept_repository
        self._artworks = artwork_repository
        self._stage_logs = stage_log_repository

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
