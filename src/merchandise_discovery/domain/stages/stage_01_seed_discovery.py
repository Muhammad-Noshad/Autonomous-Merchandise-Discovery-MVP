"""Stage 1: select promising broad identity groups from seed knowledge.

This stage is deterministic for the MVP. It ranks validated seed records by configured priority and
records a reason for every selection so later provider-backed ranking has a reproducible baseline.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import SeedItem


class SeedDiscoveryInput(BaseModel):
    """Configuration needed to select a bounded seed set."""

    seed_source: str = "mvp_seed_library"
    max_seed_items: int = Field(default=12, ge=1, le=100)


class SeedDiscoveryOutput(BaseModel):
    """Selected seed records and human-readable selection reasons."""

    selected_seeds: list[SeedItem]
    selection_reasons: dict[str, str]


def execute(input_data: SeedDiscoveryInput, seeds: list[SeedItem]) -> SeedDiscoveryOutput:
    """Select highest-priority seeds with stable tie-breaking by category and name."""

    if not seeds:
        raise ValueError("Seed discovery requires at least one seed record.")
    ordered = sorted(
        seeds,
        key=lambda seed: (
            -int(seed.metadata.get("priority", 0)),
            seed.category,
            seed.name.lower(),
        ),
    )
    selected = ordered[: input_data.max_seed_items]
    reasons = {
        seed.seed_id: (
            f"Selected from {input_data.seed_source} with priority "
            f"{seed.metadata.get('priority', 0)}."
        )
        for seed in selected
    }
    return SeedDiscoveryOutput(selected_seeds=selected, selection_reasons=reasons)
