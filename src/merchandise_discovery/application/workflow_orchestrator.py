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

    def next_runnable_stage(self, run_id: str, *, max_attempts: int = 3) -> StageExecution | None:
        """Find the earliest stage that can still be attempted under the retry policy."""

        runnable = self._stages.list_runnable(run_id, max_attempts=max_attempts)
        return runnable[0] if runnable else None

    def start_next_stage(
        self,
        run_id: str,
        *,
        max_attempts: int = 3,
    ) -> StageExecution | None:
        """Atomically mark the earliest runnable stage as running for one worker."""

        execution = self.next_runnable_stage(run_id, max_attempts=max_attempts)
        if execution is None:
            return None
        return self._stages.mark_running(execution.execution_id, execution.version)

    def fail_stage_and_run(
        self,
        run: WorkflowRun,
        execution: StageExecution,
        error_message: str,
        *,
        max_attempts: int = 3,
    ) -> None:
        """Persist failure and close the run, recording when no further retry is allowed."""

        failed_execution = self._stages.fail(execution.execution_id, execution.version, error_message)
        self._runs.update_status(
            run.run_id,
            expected_version=run.version,
            status=RunStatus.FAILED,
            current_stage_number=execution.stage_number,
            last_error=error_message,
            retry_exhausted=failed_execution.attempt_number >= max_attempts,
        )

    def complete_stage_and_run(
        self,
        run: WorkflowRun,
        execution: StageExecution,
    ) -> WorkflowRun:
        """Advance durable run progress after a stage succeeds, or close the final run."""

        completed_stages = min(run.completed_stages + 1, run.total_stages)
        is_final_stage = execution.stage_number >= run.total_stages
        return self._runs.update_status(
            run.run_id,
            expected_version=run.version,
            status=RunStatus.COMPLETED if is_final_stage else RunStatus.RUNNING,
            current_stage_number=None if is_final_stage else execution.stage_number + 1,
            last_error=None,
            completed_stages=completed_stages,
            retry_exhausted=False,
        )
