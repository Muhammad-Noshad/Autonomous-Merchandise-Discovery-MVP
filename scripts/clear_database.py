"""Drop the configured MongoDB database after an explicit destructive-action confirmation.

This utility intentionally operates at database scope: every collection and document in the
configured database is removed. It does not run the normal application initializer because that
would recreate the application metadata and indexes immediately before the drop.
"""

import argparse

from pymongo.errors import PyMongoError

from merchandise_discovery.infrastructure.mongo.client import (
    create_client,
    get_database,
    verify_connection,
)
from merchandise_discovery.shared.configuration import load_settings
from merchandise_discovery.shared.errors import ConfigurationError


def _confirm(database_name: str) -> bool:
    """Require the operator to type the exact database name before deletion."""

    print(f"WARNING: this will permanently delete the entire MongoDB database '{database_name}'.")
    print("All collections, workflow runs, stage outputs, logs, and niche records will be removed.")
    response = input(f"Type CLEAR {database_name} to continue: ")
    return response.strip() == f"CLEAR {database_name}"


def clear_database(*, confirmed: bool = False) -> None:
    """Drop the database selected by MONGODB_DATABASE and close the client safely."""

    settings = load_settings()
    if not settings.mongodb_uri:
        raise ConfigurationError(
            "MONGODB_URI is required. Refusing to run without an explicit database connection."
        )

    client = create_client(settings)
    try:
        verify_connection(client)
        database = get_database(client, settings)
        collections = database.list_collection_names()

        if not confirmed and not _confirm(settings.mongodb_database):
            print("Cancelled. No database changes were made.")
            return

        client.drop_database(settings.mongodb_database)
        print(
            f"Cleared MongoDB database '{settings.mongodb_database}' "
            f"({len(collections)} collections removed)."
        )
    finally:
        client.close()


def main() -> None:
    """Parse the explicit non-interactive flag and execute the guarded database drop."""

    parser = argparse.ArgumentParser(
        description="Permanently drop the configured Autonomous Merchandise Discovery database."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the typed confirmation; use only when the configured target is verified.",
    )
    args = parser.parse_args()

    try:
        clear_database(confirmed=args.yes)
    except (ConfigurationError, PyMongoError) as error:
        parser.error(f"Database was not cleared: {error}")


if __name__ == "__main__":
    main()
