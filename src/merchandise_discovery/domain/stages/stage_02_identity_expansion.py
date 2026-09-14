"""Stage 2: expand selected seeds into reusable identity dimensions."""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import SeedItem
from merchandise_discovery.domain.models.common import SeedCategory


class ExpandedIdentity(BaseModel):
    """One core identity or contextual dimension derived from a seed record."""

    source_seed_id: str
    source_seed_name: str
    category: SeedCategory
    dimension_type: str
    value: str
    affinity_tags: list[str] = Field(default_factory=list)
    priority: int = 0


class IdentityExpansionInput(BaseModel):
    """Selected seeds passed from Stage 1."""

    selected_seeds: list[SeedItem]


class IdentityExpansionOutput(BaseModel):
    """Expanded identity dimensions retained for downstream intersection generation."""

    identities: list[ExpandedIdentity]


def execute(input_data: IdentityExpansionInput) -> IdentityExpansionOutput:
    """Create one core identity plus configured contextual dimensions for each seed."""

    expanded: list[ExpandedIdentity] = []
    for seed in input_data.selected_seeds:
        tags = [str(tag) for tag in seed.metadata.get("affinity_tags", [])]
        priority = int(seed.metadata.get("priority", 0))
        expanded.append(
            ExpandedIdentity(
                source_seed_id=seed.seed_id,
                source_seed_name=seed.name,
                category=seed.category,
                dimension_type="core",
                value=seed.name,
                affinity_tags=tags,
                priority=priority,
            )
        )
        for dimension in seed.metadata.get("dimensions", []):
            if not isinstance(dimension, dict) or not dimension.get("value"):
                continue
            expanded.append(
                ExpandedIdentity(
                    source_seed_id=seed.seed_id,
                    source_seed_name=seed.name,
                    category=seed.category,
                    dimension_type=str(dimension.get("type", "context")),
                    value=str(dimension["value"]),
                    affinity_tags=tags,
                    priority=priority,
                )
            )
    return IdentityExpansionOutput(identities=expanded)
