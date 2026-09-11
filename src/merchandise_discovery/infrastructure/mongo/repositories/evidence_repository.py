"""Persistence operations for external research evidence."""

from pymongo.collection import Collection

from merchandise_discovery.domain.models.artifacts import ResearchEvidence
from merchandise_discovery.infrastructure.mongo.serialization import from_document, to_document


class EvidenceRepository:
    """Owns MongoDB queries for source URLs, excerpts, provenance, and research interpretations."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def insert_many(self, evidence: list[ResearchEvidence]) -> None:
        """Insert source observations while keeping provenance attached to each record."""

        if evidence:
            self._collection.insert_many([to_document(item) for item in evidence])

    def replace_for_run(self, run_id: str, evidence: list[ResearchEvidence]) -> None:
        """Replace one run's evidence snapshot so a Stage 6 retry cannot duplicate citations."""

        self._collection.delete_many({"run_id": run_id})
        self.insert_many(evidence)

    def list_for_run(self, run_id: str) -> list[ResearchEvidence]:
        """Return all source observations belonging to one workflow run."""

        return [
            item
            for document in self._collection.find({"run_id": run_id}).sort(
                [("retrieved_at", -1), ("evidence_id", 1)]
            )
            if (item := from_document(ResearchEvidence, document)) is not None
        ]

    def list_for_niche(self, niche_id: str) -> list[ResearchEvidence]:
        """Return evidence newest first so the dashboard can show the latest research context."""

        return [
            item
            for document in self._collection.find({"niche_id": niche_id}).sort(
                [("retrieved_at", -1), ("evidence_id", 1)]
            )
            if (item := from_document(ResearchEvidence, document)) is not None
        ]
