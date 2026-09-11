"""Persistence operations for candidate and validated niches."""

from pymongo.collection import Collection

from merchandise_discovery.domain.models.artifacts import Niche
from merchandise_discovery.infrastructure.mongo.serialization import from_document, to_document


class NicheRepository:
    """Owns MongoDB queries for niche hypotheses, evidence-backed opportunities, and scores."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def save(self, niche: Niche) -> Niche:
        """Upsert a niche by its stable ID so stage retries remain idempotent."""

        self._collection.replace_one(
            {"niche_id": niche.niche_id},
            to_document(niche),
            upsert=True,
        )
        return niche

    def replace_for_run(self, run_id: str, niches: list[Niche]) -> None:
        """Replace one run's niche snapshot so retries do not leave stale scores behind."""

        self._collection.delete_many({"run_id": run_id})
        if niches:
            self._collection.insert_many([to_document(niche) for niche in niches])

    def get_by_id(self, niche_id: str) -> Niche | None:
        """Fetch one niche by stable application ID."""

        return from_document(Niche, self._collection.find_one({"niche_id": niche_id}))

    def list_for_run(self, run_id: str) -> list[Niche]:
        """Return niches ordered by opportunity score, with unscored records last."""

        return [
            niche
            for document in self._collection.find({"run_id": run_id}).sort(
                [("opportunity_score", -1), ("niche_id", 1)]
            )
            if (niche := from_document(Niche, document)) is not None
        ]
