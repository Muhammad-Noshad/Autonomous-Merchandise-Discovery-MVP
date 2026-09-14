"""MongoDB client construction, health checks, and index initialization.

Only this module knows how the application creates a MongoClient. Repositories receive collections
through dependency injection, which keeps query code testable without a live database.
"""

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import CollectionInvalid

from merchandise_discovery.shared.configuration import Settings, require_mongodb_uri


def create_client(settings: Settings) -> MongoClient:
    """Create a client with a bounded connection timeout for predictable startup failures."""

    return MongoClient(
        require_mongodb_uri(settings),
        serverSelectionTimeoutMS=5_000,
        connectTimeoutMS=5_000,
    )


def get_database(client: MongoClient, settings: Settings):
    """Return the configured database without performing a network call."""

    return client[settings.mongodb_database]


def verify_connection(client: MongoClient) -> None:
    """Perform an explicit health check so connection failures are not hidden until first write."""

    client.admin.command("ping")


def initialize_database(settings: Settings) -> tuple[MongoClient, Database]:
    """Connect to MongoDB and materialize the configured database for application use.

    MongoDB creates databases lazily: a database name alone is not persisted until a collection
    exists. The metadata collection is an infrastructure marker, not business data; it makes the
    configured database visible immediately while all workflow queries remain in repositories.
    """

    client = create_client(settings)
    try:
        verify_connection(client)
        database = get_database(client, settings)
        try:
            database.create_collection("_app_metadata")
        except CollectionInvalid:
            # Multiple Streamlit sessions may initialize concurrently; an existing collection is
            # the successful outcome in that race.
            pass
        ensure_indexes(database)
        return client, database
    except Exception:
        # Do not leave a client/socket pool behind when startup fails before Streamlit caches it.
        client.close()
        raise


def ensure_indexes(database) -> None:
    """Create the indexes needed for idempotency, run lookup, and worker claiming."""

    database.runs.create_index("run_id", unique=True)
    database.runs.create_index([("status", ASCENDING), ("created_at", ASCENDING)])
    database.stage_executions.create_index("execution_id", unique=True)
    database.stage_executions.create_index(
        [("run_id", ASCENDING), ("stage_number", ASCENDING), ("attempt_number", DESCENDING)]
    )
    database.stage_logs.create_index([("run_id", ASCENDING), ("created_at", DESCENDING)])
    database.stage_logs.create_index(
        [("run_id", ASCENDING), ("stage_number", ASCENDING), ("created_at", DESCENDING)]
    )
    database.seeds.create_index([("category", ASCENDING), ("name", ASCENDING)])
    database.seeds.create_index("seed_id", unique=True)
    database.intersections.create_index([("run_id", ASCENDING), ("intersection_id", ASCENDING)])
    database.niches.create_index([("run_id", ASCENDING), ("niche_id", ASCENDING)])
    database.evidence.create_index([("niche_id", ASCENDING), ("retrieved_at", DESCENDING)])
    database.concepts.create_index([("niche_id", ASCENDING), ("overall_score", DESCENDING)])
    database.briefs.create_index([("concept_id", ASCENDING), ("created_at", DESCENDING)])
    database.artworks.create_index([("concept_id", ASCENDING), ("created_at", DESCENDING)])
    database.reviews.create_index([("artwork_id", ASCENDING), ("reviewed_at", DESCENDING)])
