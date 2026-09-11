"""Smoke tests for shared workflow contracts."""

from merchandise_discovery.domain.models.common import RunStatus, StageStatus
from merchandise_discovery.domain.models.workflow import RunConfig, WorkflowRun


def test_workflow_status_values_are_stable() -> None:
    """Stable persisted status values prevent incompatible workflow records."""

    assert RunStatus.PENDING.value == "pending"
    assert StageStatus.COMPLETED.value == "completed"


def test_mvp_run_config_has_bounded_demo_defaults() -> None:
    """The first client demo stays small until real cost and quality are measured."""

    config = RunConfig()

    assert config.max_intersections == 10
    assert config.max_researched_niches == 3
    assert config.artwork_variants_per_concept == 2


def test_workflow_run_has_a_stable_identity() -> None:
    """A generated application ID lets retries update the same durable run."""

    first = WorkflowRun(title="First run")
    second = WorkflowRun(title="Second run")

    assert first.run_id != second.run_id
    assert first.status == RunStatus.PENDING
