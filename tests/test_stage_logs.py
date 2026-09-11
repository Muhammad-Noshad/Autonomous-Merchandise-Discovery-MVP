"""Tests for append-only worker event persistence."""

from unittest.mock import Mock

from merchandise_discovery.domain.models.workflow import StageLog
from merchandise_discovery.infrastructure.mongo.repositories.stage_log_repository import (
    StageLogRepository,
)


def test_stage_log_repository_appends_and_lists_bounded_events() -> None:
    """The repository owns the run/stage log query and returns validated domain records."""

    collection = Mock()
    cursor = Mock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = [
        StageLog(run_id="run-1", stage_number=2, message="Stage started.").model_dump(mode="python")
    ]
    collection.find.return_value = cursor
    repository = StageLogRepository(collection)
    log = StageLog(run_id="run-1", stage_number=2, message="Stage started.")

    assert repository.save(log) == log
    logs = repository.list_for_run("run-1", stage_number=2, limit=10)

    collection.insert_one.assert_called_once()
    collection.find.assert_called_once_with({"run_id": "run-1", "stage_number": 2})
    cursor.sort.assert_called_once_with([("created_at", -1)])
    cursor.limit.assert_called_once_with(10)
    assert logs[0].message == "Stage started."
