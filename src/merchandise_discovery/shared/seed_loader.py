"""Load and validate version-controlled seed libraries for MongoDB startup import."""

import json
from dataclasses import dataclass
from pathlib import Path

from merchandise_discovery.domain.models.artifacts import SeedItem, SeedLibrary

DEFAULT_SEED_PATH = Path(__file__).resolve().parents[3] / "data" / "seed_knowledge.json"
COHERENT_MASHUP_SEED_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "seed_knowledge_coherent_mashups.json"
)
DEFAULT_LIBRARY_ID = "mvp_seed_library"
COHERENT_MASHUP_LIBRARY_ID = "coherent_mashups_v1"


@dataclass(frozen=True)
class SeedLibraryFixture:
    """One version-controlled library definition and its source file."""

    library: SeedLibrary
    path: Path


SEED_LIBRARY_FIXTURES = (
    SeedLibraryFixture(
        library=SeedLibrary(
            library_id=DEFAULT_LIBRARY_ID,
            name="MVP Seed Library",
            description="The broad discovery library used by the original MVP funnel.",
        ),
        path=DEFAULT_SEED_PATH,
    ),
    SeedLibraryFixture(
        library=SeedLibrary(
            library_id=COHERENT_MASHUP_LIBRARY_ID,
            name="Coherent Mashups",
            description=(
                "Curated audience, interest, and value seeds designed around shared routines, "
                "tensions, and compatible lived-experience signals."
            ),
            selection_policy="category_balanced_coherent_mashup",
        ),
        path=COHERENT_MASHUP_SEED_PATH,
    ),
)


def load_seed_fixture(path: Path = DEFAULT_SEED_PATH) -> list[SeedItem]:
    """Read a JSON seed list and validate every item before it reaches a stage handler."""

    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise TypeError("Seed fixture must contain a JSON array.")
    return [SeedItem.model_validate(item) for item in payload]


def load_seed_libraries() -> list[tuple[SeedLibrary, list[SeedItem]]]:
    """Load every registered JSON library and stamp each seed with its owning library ID."""

    loaded: list[tuple[SeedLibrary, list[SeedItem]]] = []
    for fixture in SEED_LIBRARY_FIXTURES:
        seeds = [
            seed.model_copy(update={"library_id": fixture.library.library_id})
            for seed in load_seed_fixture(fixture.path)
        ]
        library = fixture.library.model_copy(update={"seed_count": len(seeds)})
        loaded.append((library, seeds))
    return loaded
