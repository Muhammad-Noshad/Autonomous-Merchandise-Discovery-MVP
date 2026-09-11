"""Persistence operations for human approval decisions."""

from pymongo.collection import Collection

from merchandise_discovery.domain.models.artifacts import HumanReview
from merchandise_discovery.infrastructure.mongo.serialization import from_document, to_document


class ReviewRepository:
    """Owns MongoDB queries for reviewer decisions and notes."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def save(self, review: HumanReview) -> HumanReview:
        """Persist a review as an immutable decision record."""

        self._collection.insert_one(to_document(review))
        return review

    def list_for_artwork(self, artwork_id: str) -> list[HumanReview]:
        """Return all review decisions for an artwork candidate, newest first."""

        return [
            review
            for document in self._collection.find({"artwork_id": artwork_id}).sort(
                [("reviewed_at", -1), ("review_id", 1)]
            )
            if (review := from_document(HumanReview, document)) is not None
        ]
