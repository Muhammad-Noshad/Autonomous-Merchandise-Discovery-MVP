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

    def migrate_legacy_records(self, library_id: str) -> int:
        """Assign legacy records to the original library before library-scoped queries begin."""

        return self._collection.update_many(
            {"library_id": {"$exists": False}},
            {"$set": {"library_id": library_id}},
        ).modified_count

    def seed_if_missing(self, library_id: str, seeds: list[SeedItem]) -> int:
        """Insert library seeds idempotently without overwriting operator-edited Mongo records."""

        inserted = 0
        for seed in seeds:
            document = to_document(seed.model_copy(update={"library_id": library_id}))
            try:
                result = self._collection.update_one(
                    {"seed_id": seed.seed_id},
                    {"$setOnInsert": document},
                    upsert=True,
                )
            except DuplicateKeyError:
                # Another application process won the same startup race; its record is valid.
                continue
            inserted += int(result.upserted_id is not None)
        return inserted

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

    def list_all(
        self,
        *,
        library_id: str | None = None,
        category: str | None = None,
    ) -> list[SeedItem]:
        """Return seed knowledge, optionally narrowed to one identity category."""

        query = {}
        if library_id:
            query["library_id"] = library_id
        if category:
            query["category"] = category
        return [
            seed
            for document in self._collection.find(query).sort([("category", 1), ("name", 1)])
            if (seed := from_document(SeedItem, document)) is not None
        ]
