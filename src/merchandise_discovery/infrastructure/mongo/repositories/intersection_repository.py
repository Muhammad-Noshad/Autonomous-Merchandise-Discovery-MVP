"""Persistence operations for generated identity intersections."""

from pymongo.collection import Collection

from merchandise_discovery.domain.models.artifacts import IdentityIntersection
from merchandise_discovery.infrastructure.mongo.serialization import from_document, to_document


class IntersectionRepository:
    """Owns MongoDB queries for intersection candidates and filter outcomes."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def insert_many(self, intersections: list[IdentityIntersection]) -> None:
        """Persist a generated batch while retaining each candidate as an inspectable record."""

        if intersections:
            self._collection.insert_many([to_document(item) for item in intersections])

    def replace_for_run(self, run_id: str, intersections: list[IdentityIntersection]) -> None:
        """Replace one run's candidate snapshot so stage retries remain idempotent."""

        self._collection.delete_many({"run_id": run_id})
        self.insert_many(intersections)

    def list_for_run(self, run_id: str) -> list[IdentityIntersection]:
        """Return intersections in generation order for one run."""

        return [
            intersection
            for document in self._collection.find({"run_id": run_id}).sort([("_id", 1)])
            if (intersection := from_document(IdentityIntersection, document)) is not None
        ]
