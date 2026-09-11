"""Persistence operations for stage execution history and retry metadata."""

from pymongo import ReturnDocument
from pymongo.collection import Collection

from merchandise_discovery.domain.models.common import StageStatus
from merchandise_discovery.domain.models.workflow import StageExecution, utc_now
from merchandise_discovery.infrastructure.mongo.serialization import from_document, to_document
from merchandise_discovery.shared.errors import ConcurrencyError


class StageExecutionRepository:
    """Owns MongoDB queries for stage status, attempts, errors, usage, and versioning."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def create_for_run(
        self,
        run_id: str,
        definitions: list[tuple],
        *,
        enable_optional: bool = False,
    ) -> list[StageExecution]:
        """Create initial records and make optional stages queueable only when enabled."""

        executions = []
        for definition in definitions:
            number, name, optional = definition[:3]
            # Preserve compatibility with three-item callers while letting the stage registry
            # persist an explicit implementation version for future replay comparisons.
            stage_version = definition[3] if len(definition) > 3 else "0.1.0"
            executions.append(
                StageExecution(
                    run_id=run_id,
                    stage_number=number,
                    stage_name=name,
                    stage_version=stage_version,
                    status=(
                        StageStatus.PENDING
                        if not optional or enable_optional
                        else StageStatus.SKIPPED
                    ),
                )
            )
        if executions:
            self._collection.insert_many([to_document(execution) for execution in executions])
        return executions

    def get_latest(self, run_id: str, stage_number: int) -> StageExecution | None:
        """Fetch the latest attempt for one stage."""

        return from_document(
            StageExecution,
            self._collection.find_one(
                {"run_id": run_id, "stage_number": stage_number},
                sort=[("attempt_number", -1)],
            ),
        )

    def list_for_run(self, run_id: str) -> list[StageExecution]:
        """Return all stage attempts for a run in pipeline order for detail and audit views."""

        return [
            execution
            for document in self._collection.find({"run_id": run_id}).sort(
                [("stage_number", 1), ("attempt_number", -1)]
            )
            if (execution := from_document(StageExecution, document)) is not None
        ]

    def list_runnable(self, run_id: str, *, max_attempts: int = 3) -> list[StageExecution]:
        """Return eligible pending/failed stages, excluding attempts at the retry ceiling."""

        if max_attempts < 1:
            raise ValueError("Maximum stage attempts must be at least 1.")

        return [
            execution
            for document in self._collection.find(
                {
                    "run_id": run_id,
                    "status": {"$in": [StageStatus.PENDING.value, StageStatus.FAILED.value]},
                    "attempt_number": {"$lt": max_attempts},
                }
            ).sort([("stage_number", 1), ("attempt_number", 1)])
            if (execution := from_document(StageExecution, document)) is not None
        ]

    def mark_running(self, execution_id: str, expected_version: int) -> StageExecution:
        """Claim a stage execution with an atomic version check."""

        document = self._collection.find_one_and_update(
            {
                "execution_id": execution_id,
                "version": expected_version,
                "status": {"$in": [StageStatus.PENDING.value, StageStatus.FAILED.value]},
            },
            {
                "$set": {
                    "status": StageStatus.RUNNING.value,
                    "started_at": utc_now(),
                    "updated_at": utc_now(),
                    "error_message": None,
                },
                "$inc": {"attempt_number": 1, "version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise ConcurrencyError(f"Stage execution is no longer claimable: {execution_id}")
        return StageExecution.model_validate(document)

    def set_input_data(
        self,
        execution_id: str,
        expected_version: int,
        input_data: dict,
    ) -> StageExecution:
        """Persist the exact input snapshot before a stage's external or expensive work begins."""

        document = self._collection.find_one_and_update(
            {"execution_id": execution_id, "version": expected_version},
            {
                "$set": {"input_data": input_data, "updated_at": utc_now()},
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise ConcurrencyError(f"Stage input changed before execution: {execution_id}")
        return StageExecution.model_validate(document)

    def complete(
        self,
        execution_id: str,
        expected_version: int,
        output_data: dict,
        output_summary: str,
        *,
        input_data: dict | None = None,
    ) -> StageExecution:
        """Persist a successful output while preserving the exact structured result."""

        set_values = {
            "status": StageStatus.COMPLETED.value,
            "progress_current": 1,
            "progress_total": 1,
            "output_data": output_data,
            "output_summary": output_summary,
            "completed_at": utc_now(),
            "updated_at": utc_now(),
        }
        if input_data is not None:
            set_values["input_data"] = input_data
        document = self._collection.find_one_and_update(
            {"execution_id": execution_id, "version": expected_version},
            {
                "$set": set_values,
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise ConcurrencyError(f"Stage execution changed before completion: {execution_id}")
        return StageExecution.model_validate(document)

    def update_progress(
        self,
        execution_id: str,
        expected_version: int,
        progress_current: int,
        progress_total: int,
        progress_message: str,
    ) -> StageExecution:
        """Persist progress as durable UI data rather than relying on a process-local session."""

        if progress_current < 0 or progress_total < 1 or progress_current > progress_total:
            raise ValueError("Stage progress must satisfy 0 <= current <= total and total >= 1.")
        document = self._collection.find_one_and_update(
            {"execution_id": execution_id, "version": expected_version},
            {
                "$set": {
                    "progress_current": progress_current,
                    "progress_total": progress_total,
                    "progress_message": progress_message,
                    "updated_at": utc_now(),
                },
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise ConcurrencyError(f"Stage execution changed before progress update: {execution_id}")
        return StageExecution.model_validate(document)

    def fail(
        self,
        execution_id: str,
        expected_version: int,
        error_message: str,
    ) -> StageExecution:
        """Persist a bounded, user-readable failure without discarding prior attempts."""

        document = self._collection.find_one_and_update(
            {"execution_id": execution_id, "version": expected_version},
            {
                "$set": {
                    "status": StageStatus.FAILED.value,
                    "error_message": error_message[:2_000],
                    "updated_at": utc_now(),
                },
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise ConcurrencyError(f"Stage execution changed before failure update: {execution_id}")
        return StageExecution.model_validate(document)
