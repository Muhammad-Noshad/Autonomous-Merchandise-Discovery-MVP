"""Persistence operations for merchandise concepts and critiques."""

from pymongo.collection import Collection

from merchandise_discovery.domain.models.artifacts import MerchandiseConcept
from merchandise_discovery.infrastructure.mongo.serialization import from_document, to_document


class ConceptRepository:
    """Owns MongoDB queries for concept candidates, scores, verdicts, and final selection."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def save(self, concept: MerchandiseConcept) -> MerchandiseConcept:
        """Upsert a concept so critique retries update one candidate rather than duplicating it."""

        self._collection.replace_one(
            {"concept_id": concept.concept_id},
            to_document(concept),
            upsert=True,
        )
        return concept

    def list_for_niche(self, niche_id: str) -> list[MerchandiseConcept]:
        """Return concepts ranked by overall score for one niche."""

        return [
            concept
            for document in self._collection.find({"niche_id": niche_id}).sort(
                [("overall_score", -1), ("concept_id", 1)]
            )
            if (concept := from_document(MerchandiseConcept, document)) is not None
        ]
