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
from merchandise_discovery.application.review_service import ReviewService
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
from merchandise_discovery.infrastructure.mongo.repositories.review_repository import (
    ReviewRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.run_repository import RunRepository
from merchandise_discovery.infrastructure.mongo.repositories.seed_repository import SeedRepository
from merchandise_discovery.infrastructure.mongo.repositories.stage_execution_repository import (
    StageExecutionRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.stage_log_repository import (
    StageLogRepository,
)
from merchandise_discovery.infrastructure.providers.image_provider import (
    FixtureImageProvider,
    XAIImageProvider,
)
from merchandise_discovery.infrastructure.providers.reasoning_provider import (
    OpenAIReasoningProvider,
)
from merchandise_discovery.infrastructure.providers.research_provider import (
    FixtureResearchProvider,
    OpenAIWebResearchProvider,
)
from merchandise_discovery.shared.configuration import Settings
from merchandise_discovery.shared.seed_loader import load_seed_fixture


@dataclass
class ApplicationRuntime:
    """Concrete dependencies shared by the UI and worker process boundaries."""

    client: MongoClient
    database: Database
    run_repository: RunRepository
    stage_repository: StageExecutionRepository
    stage_log_repository: StageLogRepository
    max_stage_attempts: int
    stop_after_stage: int
    provider_modes: dict[str, str]
    seed_repository: SeedRepository
    intersection_repository: IntersectionRepository
    niche_repository: NicheRepository
    evidence_repository: EvidenceRepository
    concept_repository: ConceptRepository
    brief_repository: BriefRepository
    artwork_repository: ArtworkRepository
    review_repository: ReviewRepository
    discovery_service: DiscoveryService
    review_service: ReviewService
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
        stage_log_repository = StageLogRepository(database.stage_logs)
        seed_repository = SeedRepository(database.seeds)
        intersection_repository = IntersectionRepository(database.intersections)
        niche_repository = NicheRepository(database.niches)
        evidence_repository = EvidenceRepository(database.evidence)
        concept_repository = ConceptRepository(database.concepts)
        brief_repository = BriefRepository(database.briefs)
        artwork_repository = ArtworkRepository(database.artworks)
        review_repository = ReviewRepository(database.reviews)
        if not seed_repository.has_records():
            seed_repository.seed_if_empty(load_seed_fixture())
        discovery_service = DiscoveryService(
            run_repository,
            stage_repository,
            intersection_repository,
            concept_repository,
            artwork_repository=artwork_repository,
            stage_log_repository=stage_log_repository,
            niche_repository=niche_repository,
        )
        workflow_orchestrator = WorkflowOrchestrator(run_repository, stage_repository)
        review_service = ReviewService(run_repository, artwork_repository, review_repository)
        live_mode = settings.provider_mode == "live"
        research_provider = (
            OpenAIWebResearchProvider(
                settings.openai_api_key,
                settings.openai_reasoning_model,
                input_price_per_million=settings.openai_input_price_per_million,
                output_price_per_million=settings.openai_output_price_per_million,
            )
            if live_mode and settings.openai_api_key
            else FixtureResearchProvider()
        )
        reasoning_provider = (
            OpenAIReasoningProvider(
                settings.openai_api_key,
                settings.openai_reasoning_model,
                input_price_per_million=settings.openai_input_price_per_million,
                output_price_per_million=settings.openai_output_price_per_million,
            )
            if live_mode and settings.openai_api_key
            else None
        )
        image_provider = (
            XAIImageProvider(
                settings.xai_api_key,
                settings.xai_image_model,
                settings.xai_image_price,
            )
            if live_mode and settings.xai_api_key
            else FixtureImageProvider()
        )
        stage_executor = DiscoveryStageExecutor(
            seed_repository,
            intersection_repository,
            stage_repository,
            niche_repository,
            evidence_repository,
            research_provider,
            concept_repository,
            brief_repository,
            artwork_repository,
            image_provider,
            reasoning_provider=reasoning_provider,
        )
        return ApplicationRuntime(
            client=client,
            database=database,
            run_repository=run_repository,
            stage_repository=stage_repository,
            stage_log_repository=stage_log_repository,
            max_stage_attempts=settings.max_stage_attempts,
            stop_after_stage=settings.stop_after_stage,
            provider_modes={
                "research": "openai web search" if live_mode and settings.openai_api_key else "fixture",
                "reasoning": "openai structured outputs" if live_mode and settings.openai_api_key else "fixture",
                "image": "xAI image generation" if live_mode and settings.xai_api_key else "fixture",
            },
            seed_repository=seed_repository,
            intersection_repository=intersection_repository,
            niche_repository=niche_repository,
            evidence_repository=evidence_repository,
            concept_repository=concept_repository,
            brief_repository=brief_repository,
            artwork_repository=artwork_repository,
            review_repository=review_repository,
            discovery_service=discovery_service,
            review_service=review_service,
            workflow_orchestrator=workflow_orchestrator,
            stage_executor=stage_executor,
        )
    except Exception:
        # If dependency assembly fails after the client connects, do not leak its socket pool.
        client.close()
        raise
