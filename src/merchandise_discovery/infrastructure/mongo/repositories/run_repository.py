"""Persistence operations for workflow runs.

The repository owns atomic claiming and optimistic-locking updates. Application services decide why
a run should change state; this module only expresses those decisions as MongoDB operations.
"""

from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from merchandise_discovery.domain.models.common import RunStatus
from merchandise_discovery.domain.models.workflow import WorkflowRun, utc_now
from merchandise_discovery.infrastructure.mongo.serialization import from_document, to_document
from merchandise_discovery.shared.errors import (
    ConcurrencyError,
    DuplicateRecordError,
)


class RunRepository:
    """Owns MongoDB queries for run creation, claiming, status, and resume state."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def create(self, run: WorkflowRun) -> WorkflowRun:
        """Insert a run once and map duplicate run IDs to a domain-level error."""

        try:
            self._collection.insert_one(to_document(run))
        except DuplicateKeyError as error:
            raise DuplicateRecordError(f"Run already exists: {run.run_id}") from error
        return run

    def get_by_id(self, run_id: str) -> WorkflowRun | None:
        """Fetch one run by its stable application identifier."""

        return from_document(
            WorkflowRun,
            self._collection.find_one({"run_id": run_id}),
        )

    def claim_next_pending(self, worker_id: str) -> WorkflowRun | None:
        """Atomically claim the oldest pending run so two workers cannot process it together."""

        document = self._collection.find_one_and_update(
            {"status": RunStatus.PENDING.value},
            {
                "$set": {
                    "status": RunStatus.RUNNING.value,
                    "claimed_by": worker_id,
                    "current_stage_number": 1,
                    "updated_at": utc_now(),
                },
                "$inc": {"version": 1},
            },
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )
        return from_document(WorkflowRun, document)

    def update_status(
        self,
        run_id: str,
        expected_version: int,
        status: RunStatus,
        *,
        current_stage_number: int | None = None,
        last_error: str | None = None,
    ) -> WorkflowRun:
        """Update state only when the caller still owns the version it read."""

        set_values = {
            "status": status.value,
            "current_stage_number": current_stage_number,
            "last_error": last_error,
            "updated_at": utc_now(),
        }
        document = self._collection.find_one_and_update(
            {"run_id": run_id, "version": expected_version},
            {"$set": set_values, "$inc": {"version": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise ConcurrencyError(f"Run version changed before update: {run_id}")
        return WorkflowRun.model_validate(document)
