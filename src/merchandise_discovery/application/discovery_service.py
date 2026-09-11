"""Application service for starting and inspecting discovery runs.

This layer coordinates use cases; it should not contain Streamlit rendering or raw MongoDB query
syntax. Those concerns remain behind the entrypoint and repository boundaries.
"""

from merchandise_discovery.domain.models.workflow import RunConfig, WorkflowRun
from merchandise_discovery.domain.stages.registry import STAGE_DEFINITIONS
from merchandise_discovery.infrastructure.mongo.repositories.run_repository import RunRepository
from merchandise_discovery.infrastructure.mongo.repositories.stage_execution_repository import (
    StageExecutionRepository,
)


class DiscoveryService:
    """Coordinate run creation without exposing MongoDB or Streamlit to callers."""

    def __init__(
        self,
        run_repository: RunRepository,
        stage_repository: StageExecutionRepository,
    ):
        self._runs = run_repository
        self._stages = stage_repository

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
            [(definition.number, definition.name, definition.optional) for definition in STAGE_DEFINITIONS],
            enable_optional=run.config.enable_similarity_ip_check,
        )
        return run

    def get_run(self, run_id: str) -> WorkflowRun | None:
        """Return the persisted run state for dashboard reads."""

        return self._runs.get_by_id(run_id)
