"""Unit tests for repository query boundaries without requiring a live MongoDB deployment."""

from unittest.mock import Mock

import pytest
from pymongo.errors import DuplicateKeyError

from merchandise_discovery.domain.models.common import RunStatus
from merchandise_discovery.domain.models.workflow import WorkflowRun
from merchandise_discovery.infrastructure.mongo.repositories.run_repository import RunRepository
from merchandise_discovery.infrastructure.mongo.repositories.stage_execution_repository import (
    StageExecutionRepository,
)
from merchandise_discovery.shared.errors import ConcurrencyError, DuplicateRecordError


def test_run_repository_creates_and_reads_typed_records() -> None:
    """The repository serializes validated models and rehydrates Mongo documents."""

    collection = Mock()
    run = WorkflowRun(title="Repository test")
    collection.find_one.return_value = run.model_dump(mode="python")
    repository = RunRepository(collection)

    created = repository.create(run)
    loaded = repository.get_by_id(run.run_id)

    collection.insert_one.assert_called_once()
    collection.find_one.assert_called_once_with({"run_id": run.run_id})
    assert created == run
    assert loaded == run


def test_run_repository_returns_none_for_missing_record() -> None:
    """A missing optional dashboard lookup is different from a failed database operation."""

    collection = Mock()
    collection.find_one.return_value = None

    assert RunRepository(collection).get_by_id("missing") is None


def test_run_repository_lists_newest_runs_with_a_bound() -> None:
    """The history page receives a bounded, repository-owned query result."""

    collection = Mock()
    cursor = Mock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = [
        WorkflowRun(title="Newest").model_dump(mode="python"),
    ]
    collection.find.return_value = cursor

    runs = RunRepository(collection).list_recent(limit=10)

    collection.find.assert_called_once_with({})
    cursor.sort.assert_called_once_with([("created_at", -1)])
    cursor.limit.assert_called_once_with(10)
    assert [run.title for run in runs] == ["Newest"]


def test_run_repository_maps_duplicate_ids_to_domain_error() -> None:
    """Repository callers should not need to depend on PyMongo exception types."""

    collection = Mock()
    collection.insert_one.side_effect = DuplicateKeyError("duplicate")
    run = WorkflowRun(title="Duplicate test")

    with pytest.raises(DuplicateRecordError):
        RunRepository(collection).create(run)


def test_run_repository_claims_the_next_pending_run_atomically() -> None:
    """Worker claiming is expressed as one find-and-update operation."""

    collection = Mock()
    run = WorkflowRun(title="Claim test", status=RunStatus.RUNNING, claimed_by="worker-1")
    collection.find_one_and_update.return_value = run.model_dump(mode="python")

    claimed = RunRepository(collection).claim_next_pending("worker-1")

    assert claimed == run
    assert collection.find_one_and_update.call_args.kwargs["sort"] == [("created_at", 1)]


def test_run_repository_can_claim_a_failed_run_for_resume() -> None:
    """A failed run returns to the worker queue without resetting its current stage."""

    collection = Mock()
    run = WorkflowRun(title="Resume test", status=RunStatus.RUNNING, claimed_by="worker-2")
    collection.find_one_and_update.return_value = run.model_dump(mode="python")

    claimed = RunRepository(collection).claim_next_available("worker-3")

    assert claimed == run
    query = collection.find_one_and_update.call_args.args[0]
    assert query["status"] == {"$in": ["pending", "failed"]}
    assert query["retry_exhausted"] == {"$ne": True}
    assert "current_stage_number" not in collection.find_one_and_update.call_args.args[1]["$set"]


def test_run_repository_rejects_lost_optimistic_lock() -> None:
    """A stale worker must not overwrite a newer run state."""

    collection = Mock()
    collection.find_one_and_update.return_value = None
    repository = RunRepository(collection)

    with pytest.raises(ConcurrencyError):
        repository.update_status(
            "run-1",
            expected_version=3,
            status=RunStatus.COMPLETED,
        )


def test_stage_repository_initializes_optional_stage_as_skipped() -> None:
    """Disabled optional work is visible in the pipeline without entering the queue."""

    collection = Mock()
    repository = StageExecutionRepository(collection)
    definitions = [(1, "First", False), (2, "Optional", True)]

    executions = repository.create_for_run("run-1", definitions)

    inserted_documents = collection.insert_many.call_args.args[0]
    assert len(inserted_documents) == 2
    assert executions[0].status.value == "pending"
    assert executions[1].status.value == "skipped"


def test_stage_repository_persists_registry_version_and_retry_ceiling() -> None:
    """Stage records carry implementation provenance and Mongo filters exhausted attempts out."""

    collection = Mock()
    repository = StageExecutionRepository(collection)
    definitions = [(1, "First", False, "1.2.0")]
    cursor = Mock()
    cursor.sort.return_value = cursor
    cursor.__iter__ = Mock(return_value=iter([]))
    collection.find.return_value = cursor

    executions = repository.create_for_run("run-1", definitions)
    repository.list_runnable("run-1", max_attempts=3)

    assert executions[0].stage_version == "1.2.0"
    query = collection.find.call_args.args[0]
    assert query["attempt_number"] == {"$lt": 3}


def test_stage_repository_lists_attempts_in_pipeline_order() -> None:
    """The detail page gets all attempts so the UI adapter can select the latest attempt per stage."""

    collection = Mock()
    cursor = Mock()
    cursor.sort.return_value = cursor
    cursor.__iter__ = Mock(
        return_value=iter(
            [
                {
                    "run_id": "run-1",
                    "stage_number": 1,
                    "stage_name": "First",
                    "attempt_number": 0,
                },
                {
                    "run_id": "run-1",
                    "stage_number": 2,
                    "stage_name": "Second",
                    "attempt_number": 0,
                },
            ]
        )
    )
    collection.find.return_value = cursor

    executions = StageExecutionRepository(collection).list_for_run("run-1")

    collection.find.assert_called_once_with({"run_id": "run-1"})
    cursor.sort.assert_called_once_with([("stage_number", 1), ("attempt_number", -1)])
    assert [execution.stage_number for execution in executions] == [1, 2]
