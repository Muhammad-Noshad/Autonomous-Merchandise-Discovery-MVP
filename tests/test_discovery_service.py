"""Application-service tests for the live run vertical slice."""

from unittest.mock import Mock

from pydantic import BaseModel

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.domain.models.common import PipelineVariant, RunStatus
from merchandise_discovery.domain.models.workflow import RunConfig, StageExecution, WorkflowRun


class ReloadedRunConfig(BaseModel):
    """Represent a config instance created by a stale Streamlit module import."""

    seed_source: str = "mvp_seed_library"
    pipeline_variant: PipelineVariant = PipelineVariant.BASELINE
    selection_seed: int = 123
    max_intersections: int = 10
    max_researched_niches: int = 3
    concepts_per_niche: int = 5
    artwork_variants_per_concept: int = 2
    enable_similarity_ip_check: bool = False


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
    assert len(stage_repository.create_for_run.call_args.args[1]) == 18


def test_create_run_normalizes_config_from_a_stale_pydantic_class() -> None:
    """A hot-reloaded UI config remains valid for a cached service instance."""

    run_repository = Mock()
    stage_repository = Mock()
    service = DiscoveryService(run_repository, stage_repository)
    stale_config = ReloadedRunConfig(
        seed_source="custom_fixture",
        pipeline_variant=PipelineVariant.COMPACT_RESEARCH_FIRST,
        selection_seed=456,
        max_intersections=4,
    )

    run = service.create_run("Reload-safe run", config=stale_config)

    assert isinstance(run.config, RunConfig)
    assert run.config.seed_source == "custom_fixture"
    assert run.config.pipeline_variant is PipelineVariant.COMPACT_RESEARCH_FIRST
    assert run.config.selection_seed == 456
    assert run.config.max_intersections == 4
    assert run.total_stages == 9


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


def test_delete_run_cascades_through_all_run_owned_repositories() -> None:
    """Run deletion removes dependent records and the aggregate through repository boundaries."""

    run = WorkflowRun(title="Delete me", status=RunStatus.COMPLETED)
    run_repository = Mock()
    run_repository.get_by_id.return_value = run
    run_repository.delete_by_id.return_value = 1
    repositories = {
        "stages": Mock(),
        "logs": Mock(),
        "intersections": Mock(),
        "niches": Mock(),
        "evidence": Mock(),
        "concepts": Mock(),
        "briefs": Mock(),
        "artworks": Mock(),
        "reviews": Mock(),
    }
    for index, repository in enumerate(repositories.values(), start=1):
        repository.delete_for_run.return_value = index

    service = DiscoveryService(
        run_repository,
        repositories["stages"],
        repositories["intersections"],
        repositories["concepts"],
        repositories["artworks"],
        repositories["logs"],
        repositories["niches"],
        evidence_repository=repositories["evidence"],
        brief_repository=repositories["briefs"],
        review_repository=repositories["reviews"],
    )

    summary = service.delete_run(run.run_id)

    run_repository.update_status.assert_called_once_with(
        run.run_id,
        expected_version=run.version,
        status=RunStatus.CANCELLED,
        current_stage_number=run.current_stage_number,
    )
    for repository in repositories.values():
        repository.delete_for_run.assert_called_once_with(run.run_id)
    run_repository.delete_by_id.assert_called_once_with(run.run_id)
    assert summary.total_deleted == 46
    assert summary.deleted_counts["runs"] == 1


def test_delete_run_allows_active_worker_run() -> None:
    """Deletion is available for every status and cancels an active run before cleanup."""

    run = WorkflowRun(title="Active run", status=RunStatus.RUNNING)
    run_repository = Mock()
    run_repository.get_by_id.return_value = run
    run_repository.delete_by_id.return_value = 1
    repositories = [Mock() for _ in range(9)]
    for repository in repositories:
        repository.delete_for_run.return_value = 0
    service = DiscoveryService(
        run_repository,
        repositories[0],
        repositories[2],
        repositories[5],
        repositories[7],
        repositories[1],
        repositories[3],
        evidence_repository=repositories[4],
        brief_repository=repositories[6],
        review_repository=repositories[8],
    )

    summary = service.delete_run(run.run_id)

    assert summary.deleted_counts["runs"] == 1
    run_repository.update_status.assert_called_once_with(
        run.run_id,
        expected_version=run.version,
        status=RunStatus.CANCELLED,
        current_stage_number=run.current_stage_number,
    )
