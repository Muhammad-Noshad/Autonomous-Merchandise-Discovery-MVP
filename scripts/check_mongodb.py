"""Verify MongoDB connectivity and initialize the MVP database.

This command provides a deterministic setup check outside Streamlit. It uses the same initializer
as the app, so a successful check both validates the URI and materializes the configured database.
"""

from merchandise_discovery.infrastructure.mongo.client import initialize_database
from merchandise_discovery.shared.configuration import load_settings


def main() -> None:
    """Connect to MongoDB, materialize the database, and ensure workflow indexes exist."""

    settings = load_settings()
    client, _database = initialize_database(settings)
    try:
        print(f"MongoDB connection passed: {settings.mongodb_database}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
