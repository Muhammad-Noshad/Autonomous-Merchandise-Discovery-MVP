"""Stage sequencing, retry, resume, and workflow-state coordination.

The orchestrator owns control flow while each stage module owns one semantic transformation. This
prevents stage files from becoming tightly coupled to UI, persistence, or model-provider details.
"""

from merchandise_discovery.domain.models.common import RunStatus
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun
from merchandise_discovery.infrastructure.mongo.repositories.run_repository import RunRepository
from merchandise_discovery.infrastructure.mongo.repositories.stage_execution_repository import (
    StageExecutionRepository,
)


class WorkflowOrchestrator:
    """Own worker-facing run operations while stage modules remain independently portable."""

    def __init__(
        self,
        run_repository: RunRepository,
        stage_repository: StageExecutionRepository,
    ):
        self._runs = run_repository
        self._stages = stage_repository

    def claim_next_run(self, worker_id: str) -> WorkflowRun | None:
        """Claim one pending or failed run atomically; return None when the queue is empty."""

        return self._runs.claim_next_available(worker_id)

    def next_runnable_stage(self, run_id: str) -> StageExecution | None:
        """Find the earliest pending or failed stage, enabling resume after a partial run."""

        runnable = self._stages.list_runnable(run_id)
        return runnable[0] if runnable else None

    def start_next_stage(self, run_id: str) -> StageExecution | None:
        """Atomically mark the earliest runnable stage as running for one worker."""

        execution = self.next_runnable_stage(run_id)
        if execution is None:
            return None
        return self._stages.mark_running(execution.execution_id, execution.version)

    def fail_stage_and_run(
        self,
        run: WorkflowRun,
        execution: StageExecution,
        error_message: str,
    ) -> None:
        """Persist stage failure and close the claimed run so unavailable work is never left stuck."""

        self._stages.fail(execution.execution_id, execution.version, error_message)
        self._runs.update_status(
            run.run_id,
            expected_version=run.version,
            status=RunStatus.FAILED,
            current_stage_number=execution.stage_number,
            last_error=error_message,
        )
