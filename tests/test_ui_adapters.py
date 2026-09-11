"""Tests for converting persisted workflow contracts into stable UI view models."""

from merchandise_discovery.application.discovery_service import RunSnapshot
from merchandise_discovery.domain.models.common import StageStatus
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun
from merchandise_discovery.ui.adapters import snapshot_to_fixture, workflow_to_list_item


def test_snapshot_adapter_preserves_persisted_stage_state() -> None:
    """Live detail data retains status, progress, attempts, output, and errors for the UI."""

    run = WorkflowRun(title="Live detail")
    stage = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Seed discovery",
        status=StageStatus.FAILED,
        progress_current=2,
        progress_total=4,
        attempt_number=2,
        input_data={"seed_limit": 5},
        output_data={"selected_seeds": [{"seed_id": "seed-1"}]},
        error_message="Provider unavailable",
    )

    fixture = snapshot_to_fixture(RunSnapshot(run=run, stages=[stage]))

    assert fixture.current_stage_number == 1
    assert fixture.stages[0].progress == 50
    assert fixture.stages[0].metrics["Attempt"] == "2"
    assert fixture.stages[0].error_message == "Provider unavailable"
    assert fixture.stages[0].summary.startswith("Select high-value audience")
    assert fixture.stages[0].input_payload == {"seed_limit": 5}
    assert fixture.stages[0].output_payload == {"selected_seeds": [{"seed_id": "seed-1"}]}


def test_workflow_adapter_calculates_history_progress() -> None:
    """Run history derives a bounded display percentage from persisted completion counts."""

    run = WorkflowRun(title="History", completed_stages=8)

    item = workflow_to_list_item(run)

    assert item.progress == 47
