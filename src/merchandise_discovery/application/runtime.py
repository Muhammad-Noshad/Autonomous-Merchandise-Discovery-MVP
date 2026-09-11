"""Composition root for the MongoDB-backed application runtime.

This is the only place that assembles concrete repositories with application services. Streamlit
and the worker receive the resulting runtime instead of constructing collections or repositories
themselves, which keeps both entrypoints replaceable.
"""

from dataclasses import dataclass

from pymongo import MongoClient
from pymongo.database import Database

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.application.discovery_stage_executor import DiscoveryStageExecutor
from merchandise_discovery.application.workflow_orchestrator import WorkflowOrchestrator
from merchandise_discovery.infrastructure.mongo.client import initialize_database
from merchandise_discovery.infrastructure.mongo.repositories.artwork_repository import (
    ArtworkRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.brief_repository import BriefRepository
from merchandise_discovery.infrastructure.mongo.repositories.concept_repository import (
    ConceptRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.evidence_repository import (
    EvidenceRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.intersection_repository import (
    IntersectionRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.niche_repository import NicheRepository
from merchandise_discovery.infrastructure.mongo.repositories.run_repository import RunRepository
from merchandise_discovery.infrastructure.mongo.repositories.seed_repository import SeedRepository
from merchandise_discovery.infrastructure.mongo.repositories.stage_execution_repository import (
    StageExecutionRepository,
)
from merchandise_discovery.infrastructure.providers.image_provider import FixtureImageProvider
from merchandise_discovery.infrastructure.providers.research_provider import FixtureResearchProvider
from merchandise_discovery.shared.configuration import Settings


@dataclass
class ApplicationRuntime:
    """Concrete dependencies shared by the UI and worker process boundaries."""

    client: MongoClient
    database: Database
    run_repository: RunRepository
    stage_repository: StageExecutionRepository
    seed_repository: SeedRepository
    intersection_repository: IntersectionRepository
    niche_repository: NicheRepository
    evidence_repository: EvidenceRepository
    concept_repository: ConceptRepository
    brief_repository: BriefRepository
    artwork_repository: ArtworkRepository
    discovery_service: DiscoveryService
    workflow_orchestrator: WorkflowOrchestrator
    stage_executor: DiscoveryStageExecutor

    def close(self) -> None:
        """Release the MongoDB connection pool when the process boundary shuts down."""

        self.client.close()


def build_runtime(settings: Settings) -> ApplicationRuntime:
    """Build the database-backed runtime after verifying MongoDB and preparing its indexes."""

    client, database = initialize_database(settings)
    try:
        run_repository = RunRepository(database.runs)
        stage_repository = StageExecutionRepository(database.stage_executions)
        seed_repository = SeedRepository(database.seeds)
        intersection_repository = IntersectionRepository(database.intersections)
        niche_repository = NicheRepository(database.niches)
        evidence_repository = EvidenceRepository(database.evidence)
        concept_repository = ConceptRepository(database.concepts)
        brief_repository = BriefRepository(database.briefs)
        artwork_repository = ArtworkRepository(database.artworks)
        discovery_service = DiscoveryService(
            run_repository,
            stage_repository,
            intersection_repository,
            concept_repository,
            artwork_repository=artwork_repository,
        )
        workflow_orchestrator = WorkflowOrchestrator(run_repository, stage_repository)
        stage_executor = DiscoveryStageExecutor(
            seed_repository,
            intersection_repository,
            stage_repository,
            niche_repository,
            evidence_repository,
            FixtureResearchProvider(),
            concept_repository,
            brief_repository,
            artwork_repository,
            FixtureImageProvider(),
        )
        return ApplicationRuntime(
            client=client,
            database=database,
            run_repository=run_repository,
            stage_repository=stage_repository,
            seed_repository=seed_repository,
            intersection_repository=intersection_repository,
            niche_repository=niche_repository,
            evidence_repository=evidence_repository,
            concept_repository=concept_repository,
            brief_repository=brief_repository,
            artwork_repository=artwork_repository,
            discovery_service=discovery_service,
            workflow_orchestrator=workflow_orchestrator,
            stage_executor=stage_executor,
        )
    except Exception:
        # If dependency assembly fails after the client connects, do not leak its socket pool.
        client.close()
        raise
