"""MongoDB query boundary for append-only workflow event logs."""

from pymongo.collection import Collection

from merchandise_discovery.domain.models.workflow import StageLog
from merchandise_discovery.infrastructure.mongo.serialization import from_document, to_document


class StageLogRepository:
    """Persist worker lifecycle messages without coupling callers to MongoDB query syntax."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def save(self, log: StageLog) -> StageLog:
        """Append one validated event; existing events are never updated or deleted."""

        self._collection.insert_one(to_document(log))
        return log

    def list_for_run(
        self,
        run_id: str,
        *,
        stage_number: int | None = None,
        limit: int = 100,
    ) -> list[StageLog]:
        """Return newest bounded events, optionally narrowed to one stage."""

        if limit < 1:
            raise ValueError("Log limit must be at least 1.")
        query = {"run_id": run_id}
        if stage_number is not None:
            query["stage_number"] = stage_number
        return [
            log
            for document in self._collection.find(query).sort([("created_at", -1)]).limit(limit)
            if (log := from_document(StageLog, document)) is not None
        ]
