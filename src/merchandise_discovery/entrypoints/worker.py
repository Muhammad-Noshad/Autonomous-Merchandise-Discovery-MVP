"""Command-line entrypoint for the background workflow worker."""

import argparse


def main() -> None:
    """Parse worker options; actual run claiming is added with the workflow implementation."""

    parser = argparse.ArgumentParser(description="Run the merchandise discovery worker.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Claim and execute one pending run when worker execution is implemented.",
    )
    parser.parse_args()
    raise SystemExit("Worker execution is not implemented in chunk one.")

