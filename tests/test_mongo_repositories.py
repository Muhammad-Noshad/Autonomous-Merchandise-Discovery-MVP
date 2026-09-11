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
