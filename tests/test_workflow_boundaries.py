"""Regression tests for the intentional MVP stop boundary and Mongo-backed niche use case."""

from unittest.mock import Mock

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.application.workflow_orchestrator import WorkflowOrchestrator
from merchandise_discovery.domain.models.common import RunStatus, StageStatus
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun


def test_complete_stage_pauses_at_configured_mvp_boundary() -> None:
    """A deliberate Stage 1 stop must be durable and must not look like a running queue item."""

    runs = Mock()
    stages = Mock()
    orchestrator = WorkflowOrchestrator(runs, stages)
    run = WorkflowRun(title="Stage 1 demo", status=RunStatus.RUNNING, version=4)
    execution = StageExecution(
        run_id=run.run_id,
        stage_number=1,
        stage_name="Autonomous Seed Discovery",
        status=StageStatus.COMPLETED,
    )
    paused_run = run.model_copy(
        update={
            "status": RunStatus.PAUSED,
            "completed_stages": 1,
            "current_stage_number": 1,
        }
    )
    runs.update_status.return_value = paused_run

    result = orchestrator.complete_stage_and_run(run, execution, stop_after_stage=1)

    assert result.status == RunStatus.PAUSED
    runs.update_status.assert_called_once_with(
        run.run_id,
        expected_version=run.version,
        status=RunStatus.PAUSED,
        current_stage_number=1,
        last_error=None,
        completed_stages=1,
        retry_exhausted=False,
    )


def test_create_manual_niche_delegates_to_repository_for_existing_run() -> None:
    """Manual niche input receives the selected run ID before it reaches MongoDB."""

    runs = Mock()
    niches = Mock()
    run = WorkflowRun(title="Niche demo")
    runs.get_by_id.return_value = run
    niches.save.side_effect = lambda niche: niche
    service = DiscoveryService(runs, Mock(), niche_repository=niches)

    created = service.create_manual_niche(
        run.run_id,
        name="Night shift nurses",
        experience_summary="Decompressing after a long shift.",
        coherence_score=8.5,
        opportunity_score=72.0,
    )

    assert created.run_id == run.run_id
    assert created.name == "Night shift nurses"
    assert created.coherence_score == 8.5
    assert created.opportunity_score == 72.0
    niches.save.assert_called_once_with(created)
