"""MongoDB queries for selectable seed-library metadata."""

from pymongo.collection import Collection

from merchandise_discovery.domain.models.artifacts import SeedLibrary
from merchandise_discovery.infrastructure.mongo.serialization import from_document


class SeedLibraryRepository:
    """Own the catalog of seed packs presented by the Create Run page."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def ensure(self, library: SeedLibrary) -> None:
        """Upsert library metadata while retaining the original creation timestamp."""

        document = library.model_dump(mode="python")
        created_at = document.pop("created_at")
        self._collection.update_one(
            {"library_id": library.library_id},
            {
                "$set": document,
                "$setOnInsert": {"created_at": created_at},
            },
            upsert=True,
        )

    def list_active(self) -> list[SeedLibrary]:
        """Return active libraries in the stable order used by the run-creation dropdown."""

        return [
            library
            for document in self._collection.find({"active": True}).sort("name", 1)
            if (library := from_document(SeedLibrary, document)) is not None
        ]
