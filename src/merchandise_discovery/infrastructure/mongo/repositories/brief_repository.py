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

    def get_by_concept(self, concept_id: str) -> DesignBrief | None:
        """Fetch the current brief for one concept."""

        return from_document(DesignBrief, self._collection.find_one({"concept_id": concept_id}))

