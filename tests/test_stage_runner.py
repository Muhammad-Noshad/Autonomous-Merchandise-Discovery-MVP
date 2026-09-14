"""Unit tests for execute_stage helper."""

from unittest.mock import Mock

import pytest

from merchandise_discovery.application.stage_executor import StageResult
from merchandise_discovery.application.stage_runner import execute_stage
from merchandise_discovery.domain.models.common import RunStatus, StageStatus
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun


def test_execute_stage_success() -> None:
    """execute_stage coordinates prepare, execute, complete, and log successfully."""

    runtime = Mock()
    run = WorkflowRun(title="Test run", status=RunStatus.RUNNING)
    execution = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Seed Discovery",
        status=StageStatus.RUNNING,
    )
    input_payload = {"seed_source": "mvp_seed_library", "max_seed_items": 10}
    runtime.stage_executor.prepare.return_value = input_payload
    runtime.stage_repository.set_input_data.return_value = execution
    stage_result = StageResult(
        input_data=input_payload,
        output_data={"selected_seeds": []},
        output_summary="Selected 0 seeds.",
    )
    runtime.stage_executor.execute.return_value = stage_result
    completed_execution = execution.model_copy(update={"status": StageStatus.COMPLETED})
    runtime.stage_repository.complete.return_value = completed_execution
    completed_run = run.model_copy(update={"completed_stages": 1, "current_stage_number": 2})
    runtime.workflow_orchestrator.complete_stage_and_run.return_value = completed_run

    updated_run, returned_exec, result = execute_stage(runtime, run, execution)

    runtime.stage_executor.prepare.assert_called_once_with(run, execution)
    runtime.stage_repository.set_input_data.assert_called_once_with(
        execution.execution_id, execution.version, input_payload
    )
    runtime.stage_executor.execute.assert_called_once_with(run, execution, input_payload)
    runtime.stage_repository.complete.assert_called_once()
    runtime.stage_log_repository.save.assert_called_once()
    runtime.workflow_orchestrator.complete_stage_and_run.assert_called_once_with(run, completed_execution)
    assert updated_run == completed_run
    assert result == stage_result


def test_execute_stage_failure_marks_stage_and_run_failed() -> None:
    """When a stage fails during execution, failure is persisted and exception re-raised."""

    runtime = Mock()
    runtime.max_stage_attempts = 3
    run = WorkflowRun(title="Test run", status=RunStatus.RUNNING)
    execution = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Seed Discovery",
        status=StageStatus.RUNNING,
    )
    runtime.stage_executor.prepare.side_effect = RuntimeError("Stage execution error")

    with pytest.raises(RuntimeError, match="Stage execution error"):
        execute_stage(runtime, run, execution)

    runtime.workflow_orchestrator.fail_stage_and_run.assert_called_once_with(
        run, execution, "Stage execution error", max_attempts=3
    )
    runtime.stage_log_repository.save.assert_called_once()
