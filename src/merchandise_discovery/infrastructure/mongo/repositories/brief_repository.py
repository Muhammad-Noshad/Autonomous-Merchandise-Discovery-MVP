"""Persistence operations for structured design briefs."""

from pymongo.collection import Collection

from merchandise_discovery.domain.models.artifacts import DesignBrief
from merchandise_discovery.infrastructure.mongo.serialization import from_document, to_document


class BriefRepository:
    """Owns MongoDB queries for design briefs linked to selected concepts."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def save(self, brief: DesignBrief) -> DesignBrief:
        """Upsert a brief so prompt compilation can be repeated safely."""

        self._collection.replace_one(
            {"brief_id": brief.brief_id},
            to_document(brief),
            upsert=True,
        )
        return brief

    def replace_for_run(self, run_id: str, briefs: list[DesignBrief]) -> None:
        """Replace one run's brief snapshot so prompt retries remain idempotent."""

        self._collection.delete_many({"run_id": run_id})
        if briefs:
            self._collection.insert_many([to_document(brief) for brief in briefs])

    def list_for_run(self, run_id: str) -> list[DesignBrief]:
        """Return all briefs belonging to one run."""

        return [
            brief
            for document in self._collection.find({"run_id": run_id}).sort([("brief_id", 1)])
            if (brief := from_document(DesignBrief, document)) is not None
        ]

    def get_by_concept(self, concept_id: str) -> DesignBrief | None:
        """Fetch the current brief for one concept."""

        return from_document(DesignBrief, self._collection.find_one({"concept_id": concept_id}))
