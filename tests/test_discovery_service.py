"""Application-service tests for the live run vertical slice."""

from unittest.mock import Mock

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.domain.models.workflow import RunConfig, StageExecution, WorkflowRun


def test_create_run_persists_configured_run_and_stage_records() -> None:
    """The service owns aggregate creation and initializes all stage records through repositories."""

    run_repository = Mock()
    stage_repository = Mock()
    service = DiscoveryService(run_repository, stage_repository)
    config = RunConfig(seed_source="custom_fixture", max_intersections=4)

    run = service.create_run("Client demo", config=config, triggered_by="manual")

    run_repository.create.assert_called_once_with(run)
    stage_repository.create_for_run.assert_called_once()
    assert run.title == "Client demo"
    assert run.config == config
    assert len(stage_repository.create_for_run.call_args.args[1]) == 17


def test_get_run_snapshot_combines_run_and_stage_reads() -> None:
    """The UI receives one application-level snapshot instead of coordinating repository calls."""

    run_repository = Mock()
    stage_repository = Mock()
    run = WorkflowRun(title="Snapshot")
    stages = [StageExecution(run_id=run.run_id, stage_number=1, stage_name="First")]
    run_repository.get_by_id.return_value = run
    stage_repository.list_for_run.return_value = stages

    snapshot = DiscoveryService(run_repository, stage_repository).get_run_snapshot(run.run_id)

    assert snapshot is not None
    assert snapshot.run == run
    assert snapshot.stages == stages
