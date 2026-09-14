"""Stage 2: expand selected seeds into reusable identity dimensions.

The provider contract is intentionally separate from the downstream identity model. OpenAI returns
only semantic dimensions keyed by trusted seed IDs; this module validates that response and merges
application-owned source metadata before later stages consume it.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import SeedItem
from merchandise_discovery.domain.models.common import SeedCategory


class DimensionType(str, Enum):
    """Controlled semantic labels accepted from the Stage 2 reasoning provider."""

    ROUTINE = "routine"
    TENSION = "tension"
    LANGUAGE = "language"
    RITUAL = "ritual"
    BEHAVIOR = "behavior"
    EMOTION = "emotion"
    PREFERENCE = "preference"
    CONTEXT = "context"


class GeneratedDimension(BaseModel):
    """One provider-generated experience dimension before source metadata is merged."""

    dimension_type: DimensionType
    value: str = Field(min_length=1, max_length=240)
    affinity_tags: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0, le=1)
    merchandise_relevance: int = Field(ge=1, le=10)
    rationale: str = Field(min_length=1, max_length=320)


class SeedExpansion(BaseModel):
    """Provider-generated dimensions linked to exactly one input seed."""

    source_seed_id: str = Field(min_length=1)
    dimensions: list[GeneratedDimension] = Field(min_length=4, max_length=6)


class Stage2ReasoningOutput(BaseModel):
    """Exact structured response expected from OpenAI for Stage 2."""

    expansions: list[SeedExpansion] = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=500)


class ExpandedIdentity(BaseModel):
    """One core identity or contextual dimension derived from a seed record."""

    source_seed_id: str
    source_seed_name: str
    category: SeedCategory
    dimension_type: str
    value: str
    affinity_tags: list[str] = Field(default_factory=list)
    priority: int = 0
    confidence: float | None = Field(default=None, ge=0, le=1)
    merchandise_relevance: int | None = Field(default=None, ge=1, le=10)
    rationale: str | None = None
    provenance: Literal["seed_metadata", "provider"] = "seed_metadata"


class IdentityExpansionInput(BaseModel):
    """Selected seeds passed from Stage 1."""

    selected_seeds: list[SeedItem]


class IdentityExpansionOutput(BaseModel):
    """Expanded identity dimensions retained for downstream intersection generation."""

    identities: list[ExpandedIdentity]
    provider_expansions: list[dict] = Field(default_factory=list)
    summary: str = ""
    model: str = "deterministic"


def _normalized_value(value: str) -> str:
    """Normalize text for duplicate suppression without changing the displayed value."""

    return " ".join(value.casefold().split())


def _seed_tags(seed: SeedItem) -> list[str]:
    """Read the seed's trusted tags for inheritance by its expanded dimensions."""

    return [str(tag).strip() for tag in seed.metadata.get("affinity_tags", []) if str(tag).strip()]


def _validate_provider_links(
    selected_seeds: list[SeedItem],
    reasoning_output: Stage2ReasoningOutput,
) -> dict[str, SeedExpansion]:
    """Ensure the provider returned one expansion for every input seed and no invented IDs."""

    expected_ids = {seed.seed_id for seed in selected_seeds}
    returned_ids = [item.source_seed_id for item in reasoning_output.expansions]
    if len(returned_ids) != len(set(returned_ids)):
        raise ValueError("Stage 2 provider output contains duplicate source seed IDs.")
    returned_id_set = set(returned_ids)
    unknown_ids = returned_id_set - expected_ids
    missing_ids = expected_ids - returned_id_set
    if unknown_ids:
        raise ValueError(f"Stage 2 provider output contains unknown seed IDs: {sorted(unknown_ids)}.")
    if missing_ids:
        raise ValueError(f"Stage 2 provider output is missing seed IDs: {sorted(missing_ids)}.")
    return {item.source_seed_id: item for item in reasoning_output.expansions}


def execute(
    input_data: IdentityExpansionInput,
    reasoning_output: Stage2ReasoningOutput | None = None,
    model: str = "deterministic",
) -> IdentityExpansionOutput:
    """Create trusted core identities plus metadata or provider-generated dimensions."""

    expanded: list[ExpandedIdentity] = []
    provider_by_seed = (
        _validate_provider_links(input_data.selected_seeds, reasoning_output)
        if reasoning_output is not None
        else {}
    )
    for seed in input_data.selected_seeds:
        tags = _seed_tags(seed)
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
        if reasoning_output is not None:
            seen_values = {_normalized_value(seed.name)}
            for dimension in provider_by_seed[seed.seed_id].dimensions:
                normalized_value = _normalized_value(dimension.value)
                if normalized_value in seen_values:
                    continue
                seen_values.add(normalized_value)
                generated_tags = [tag.strip() for tag in dimension.affinity_tags if tag.strip()]
                expanded.append(
                    ExpandedIdentity(
                        source_seed_id=seed.seed_id,
                        source_seed_name=seed.name,
                        category=seed.category,
                        dimension_type=dimension.dimension_type.value,
                        value=dimension.value.strip(),
                        affinity_tags=list(dict.fromkeys(tags + generated_tags)),
                        priority=priority,
                        confidence=dimension.confidence,
                        merchandise_relevance=dimension.merchandise_relevance,
                        rationale=dimension.rationale,
                        provenance="provider",
                    )
                )
            continue

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
    return IdentityExpansionOutput(
        identities=expanded,
        provider_expansions=(
            [item.model_dump(mode="python") for item in reasoning_output.expansions]
            if reasoning_output is not None
            else []
        ),
        summary=reasoning_output.summary if reasoning_output is not None else "",
        model=model,
    )
