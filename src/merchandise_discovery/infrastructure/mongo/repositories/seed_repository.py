"""Persistence operations for seed knowledge."""

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

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

    def has_records(self) -> bool:
        """Check whether the knowledge-base collection already contains any seed document."""

        return self._collection.find_one({}, projection={"_id": 1}) is not None

    def seed_if_empty(self, seeds: list[SeedItem]) -> bool:
        """Insert the initial seed set only when no seed exists; return whether insertion occurred."""

        if self.has_records():
            return False
        if not seeds:
            raise ValueError("Cannot seed the knowledge base with an empty seed list.")
        try:
            self._collection.insert_many([to_document(seed) for seed in seeds])
        except DuplicateKeyError:
            # A second process may pass the empty check concurrently. The unique seed_id index
            # makes the first initializer authoritative and the later initializer harmless.
            return False
        return True

    def list_all(self, *, category: str | None = None) -> list[SeedItem]:
        """Return seed knowledge, optionally narrowed to one identity category."""

        query = {"category": category} if category else {}
        return [
            seed
            for document in self._collection.find(query).sort([("category", 1), ("name", 1)])
            if (seed := from_document(SeedItem, document)) is not None
        ]
