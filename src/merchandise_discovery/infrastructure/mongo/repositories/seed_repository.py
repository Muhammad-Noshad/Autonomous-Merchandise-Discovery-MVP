"""Persistence operations for seed knowledge."""

from pymongo.collection import Collection

from merchandise_discovery.domain.models.artifacts import SeedItem
from merchandise_discovery.infrastructure.mongo.serialization import from_document, to_document


class SeedRepository:
    """Owns MongoDB queries for occupations, hobbies, identities, and relationships."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def replace_all(self, seeds: list[SeedItem]) -> None:
        """Replace the imported seed set as one explicit administrative operation."""

        self._collection.delete_many({})
        if seeds:
            self._collection.insert_many([to_document(seed) for seed in seeds])

    def list_all(self, *, category: str | None = None) -> list[SeedItem]:
        """Return seed knowledge, optionally narrowed to one identity category."""

        query = {"category": category} if category else {}
        return [
            seed
            for document in self._collection.find(query).sort([("category", 1), ("name", 1)])
            if (seed := from_document(SeedItem, document)) is not None
        ]
