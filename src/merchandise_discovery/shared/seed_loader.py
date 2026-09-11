"""Load and validate the small seed fixture used by the deterministic discovery funnel."""

import json
from pathlib import Path

from merchandise_discovery.domain.models.artifacts import SeedItem

DEFAULT_SEED_PATH = Path(__file__).resolve().parents[3] / "data" / "seed_knowledge.json"


def load_seed_fixture(path: Path = DEFAULT_SEED_PATH) -> list[SeedItem]:
    """Read a JSON seed list and validate every item before it reaches a stage handler."""

    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise TypeError("Seed fixture must contain a JSON array.")
    return [SeedItem.model_validate(item) for item in payload]
