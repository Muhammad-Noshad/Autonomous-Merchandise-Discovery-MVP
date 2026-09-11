"""Unit tests for MongoDB startup behavior without requiring a live MongoDB deployment."""

from unittest.mock import Mock, patch

from merchandise_discovery.infrastructure.mongo.client import initialize_database
from merchandise_discovery.shared.configuration import Settings


def test_initialize_database_materializes_database_and_indexes() -> None:
    """Startup creates the infrastructure collection before preparing repository indexes."""

    client = Mock()
    database = Mock()
    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="test_database",
        openai_api_key=None,
        xai_api_key=None,
        xai_image_model="grok-imagine-image",
    )

    with (
        patch("merchandise_discovery.infrastructure.mongo.client.create_client", return_value=client),
        patch(
            "merchandise_discovery.infrastructure.mongo.client.get_database",
            return_value=database,
        ),
    ):
        initialized_client, initialized_database = initialize_database(settings)

    assert initialized_client is client
    assert initialized_database is database
    database.create_collection.assert_called_once_with("_app_metadata")
    assert database.runs.create_index.called

