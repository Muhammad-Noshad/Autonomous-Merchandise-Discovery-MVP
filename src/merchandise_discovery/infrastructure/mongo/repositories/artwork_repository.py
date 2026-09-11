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

    def list_for_concept(self, concept_id: str) -> list[Artwork]:
        """Return artwork attempts in creation order for side-by-side review."""

        return [
            artwork
            for document in self._collection.find({"concept_id": concept_id}).sort(
                [("created_at", 1), ("artwork_id", 1)]
            )
            if (artwork := from_document(Artwork, document)) is not None
        ]

