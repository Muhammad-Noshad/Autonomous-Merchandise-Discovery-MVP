"""Composition root for the MongoDB-backed application runtime.

This is the only place that assembles concrete repositories with application services. Streamlit
and the worker receive the resulting runtime instead of constructing collections or repositories
themselves, which keeps both entrypoints replaceable.
"""

from dataclasses import dataclass

from pymongo import MongoClient
from pymongo.database import Database

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.application.workflow_orchestrator import WorkflowOrchestrator
from merchandise_discovery.infrastructure.mongo.client import initialize_database
from merchandise_discovery.infrastructure.mongo.repositories.run_repository import RunRepository
from merchandise_discovery.infrastructure.mongo.repositories.stage_execution_repository import (
    StageExecutionRepository,
)
from merchandise_discovery.shared.configuration import Settings


@dataclass
class ApplicationRuntime:
    """Concrete dependencies shared by the UI and worker process boundaries."""

    client: MongoClient
    database: Database
    run_repository: RunRepository
    stage_repository: StageExecutionRepository
    discovery_service: DiscoveryService
    workflow_orchestrator: WorkflowOrchestrator

    def close(self) -> None:
        """Release the MongoDB connection pool when the process boundary shuts down."""

        self.client.close()


def build_runtime(settings: Settings) -> ApplicationRuntime:
    """Build the database-backed runtime after verifying MongoDB and preparing its indexes."""

    client, database = initialize_database(settings)
    try:
        run_repository = RunRepository(database.runs)
        stage_repository = StageExecutionRepository(database.stage_executions)
        discovery_service = DiscoveryService(run_repository, stage_repository)
        workflow_orchestrator = WorkflowOrchestrator(run_repository, stage_repository)
        return ApplicationRuntime(
            client=client,
            database=database,
            run_repository=run_repository,
            stage_repository=stage_repository,
            discovery_service=discovery_service,
            workflow_orchestrator=workflow_orchestrator,
        )
    except Exception:
        # If dependency assembly fails after the client connects, do not leak its socket pool.
        client.close()
        raise
