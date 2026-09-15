"""Persistence operations for artwork metadata and generation attempts."""

from pymongo.collection import Collection

from merchandise_discovery.domain.models.artifacts import Artwork
from merchandise_discovery.infrastructure.mongo.serialization import from_document, to_document


class ArtworkRepository:
    """Owns MongoDB queries for briefs, prompts, image candidates, and artwork QA outcomes."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def save(self, artwork: Artwork) -> Artwork:
        """Upsert artwork metadata while keeping the binary file outside MongoDB."""

        self._collection.replace_one(
            {"artwork_id": artwork.artwork_id},
            to_document(artwork),
            upsert=True,
        )
        return artwork

    def replace_for_run(self, run_id: str, artworks: list[Artwork]) -> None:
        """Replace one run's artwork snapshot so generation retries do not duplicate variants."""

        self._collection.delete_many({"run_id": run_id})
        if artworks:
            self._collection.insert_many([to_document(artwork) for artwork in artworks])

    def get_by_id(self, artwork_id: str) -> Artwork | None:
        """Fetch one artwork so the application can enforce run ownership before review."""

        return from_document(Artwork, self._collection.find_one({"artwork_id": artwork_id}))

    def list_for_run(self, run_id: str) -> list[Artwork]:
        """Return artwork candidates in generation order for the review page."""

        return [
            artwork
            for document in self._collection.find({"run_id": run_id}).sort(
                [("created_at", 1), ("artwork_id", 1)]
            )
            if (artwork := from_document(Artwork, document)) is not None
        ]

    def delete_for_run(self, run_id: str) -> int:
        """Delete artwork metadata owned by one run; external object files are separate storage."""

        return self._collection.delete_many({"run_id": run_id}).deleted_count

    def list_for_concept(self, concept_id: str) -> list[Artwork]:
        """Return artwork attempts in creation order for side-by-side review."""

        return [
            artwork
            for document in self._collection.find({"concept_id": concept_id}).sort(
                [("created_at", 1), ("artwork_id", 1)]
            )
            if (artwork := from_document(Artwork, document)) is not None
        ]
