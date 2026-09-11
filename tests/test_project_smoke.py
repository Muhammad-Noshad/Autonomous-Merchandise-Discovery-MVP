"""Smoke tests for the chunk-one project boundary."""

from merchandise_discovery.domain.models.common import RunStatus, StageStatus


def test_workflow_status_values_are_stable() -> None:
    """Stable persisted status values prevent incompatible workflow records."""

    assert RunStatus.PENDING.value == "pending"
    assert StageStatus.COMPLETED.value == "completed"

