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

    def replace_for_run(self, run_id: str, concepts: list[MerchandiseConcept]) -> None:
        """Replace one run's concept snapshot so stage retries do not duplicate candidates."""

        self._collection.delete_many({"run_id": run_id})
        if concepts:
            self._collection.insert_many([to_document(concept) for concept in concepts])

    def list_for_run(self, run_id: str) -> list[MerchandiseConcept]:
        """Return all concepts for a run, with finalists and strongest scores first."""

        return [
            concept
            for document in self._collection.find({"run_id": run_id}).sort(
                [("selected", -1), ("overall_score", -1), ("concept_id", 1)]
            )
            if (concept := from_document(MerchandiseConcept, document)) is not None
        ]

    def delete_for_run(self, run_id: str) -> int:
        """Delete all merchandise concepts generated for one run."""

        return self._collection.delete_many({"run_id": run_id}).deleted_count

    def list_for_niche(self, niche_id: str) -> list[MerchandiseConcept]:
        """Return concepts ranked by overall score for one niche."""

        return [
            concept
            for document in self._collection.find({"niche_id": niche_id}).sort(
                [("overall_score", -1), ("concept_id", 1)]
            )
            if (concept := from_document(MerchandiseConcept, document)) is not None
        ]
