"""Inline and service-level execution helpers for workflow stages.

This helper encapsulates preparing, executing, persisting, and logging a single stage execution,
ensuring consistent behavior between background workers and UI-triggered inline stage execution.
"""

import logging

from merchandise_discovery.application.runtime import ApplicationRuntime
from merchandise_discovery.application.stage_executor import StageResult
from merchandise_discovery.domain.models.workflow import StageExecution, StageLog, WorkflowRun
from merchandise_discovery.shared.logging import (
    stage_ended,
    stage_error,
    stage_progress,
    stage_started,
)

logger = logging.getLogger(__name__)


def execute_stage(
    runtime: ApplicationRuntime,
    run: WorkflowRun,
    execution: StageExecution,
) -> tuple[WorkflowRun, StageExecution, StageResult]:
    """Execute one claimed stage execution to completion, persisting output snapshots and logs."""

    active_execution = execution
    stage_started(execution, run.run_id)
    try:
        input_data = runtime.stage_executor.prepare(run, execution)
        stage_progress(execution, "Input prepared")
        active_execution = runtime.stage_repository.set_input_data(
            execution.execution_id,
            execution.version,
            input_data,
        )
        result = runtime.stage_executor.execute(run, active_execution, input_data)
        stage_progress(execution, f"Logic complete | {result.output_summary}")
        active_execution = runtime.stage_repository.complete(
            active_execution.execution_id,
            active_execution.version,
            result.output_data,
            result.output_summary,
            input_data=result.input_data,
            usage=result.usage,
        )
        stage_progress(execution, "Output persisted")
        if runtime.stage_log_repository:
            try:
                runtime.stage_log_repository.save(
                    StageLog(
                        run_id=run.run_id,
                        stage_number=active_execution.stage_number,
                        execution_id=active_execution.execution_id,
                        level="info",
                        message=f"Stage {active_execution.stage_number} completed: {result.output_summary}",
                    )
                )
            except Exception as log_err:  # noqa: BLE001  # Logging must not mask stage state.
                logger.warning("Could not persist stage log: %s", log_err)

        updated_run = runtime.workflow_orchestrator.complete_stage_and_run(
            run,
            active_execution,
            stop_after_stage=runtime.stop_after_stage,
        )
        stage_ended(active_execution, result.output_summary)
        return updated_run, active_execution, result
    except Exception as error:
        runtime.workflow_orchestrator.fail_stage_and_run(
            run,
            active_execution,
            str(error),
            max_attempts=runtime.max_stage_attempts,
        )
        if runtime.stage_log_repository:
            try:
                runtime.stage_log_repository.save(
                    StageLog(
                        run_id=run.run_id,
                        stage_number=active_execution.stage_number,
                        execution_id=active_execution.execution_id,
                        level="error",
                        message=f"Stage {active_execution.stage_number} failed: {error}",
                    )
                )
            except Exception as log_err:  # noqa: BLE001  # Logging must not mask stage state.
                logger.warning("Could not persist stage log: %s", log_err)
        stage_error(active_execution, error)
        raise
