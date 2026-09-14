"""Stage 1: select a reproducible, category-balanced sample from seed knowledge.

The MVP deliberately uses a uniform seeded shuffle instead of priority weighting. Every run can
explore a different subset, while its persisted selection seed makes the exact result repeatable.
"""

import random

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import SeedItem
from merchandise_discovery.domain.models.common import SeedCategory


class SeedDiscoveryInput(BaseModel):
    """Configuration needed to select a bounded seed set."""

    seed_source: str = "mvp_seed_library"
    max_seed_items: int = Field(default=12, ge=1, le=100)
    selection_seed: int = Field(default=0, ge=0, le=4_294_967_295)


class SeedAnalysis(BaseModel):
    """Structured evaluation of a candidate seed from the reasoning provider."""

    seed_id: str
    seed_name: str
    category: SeedCategory
    self_identification_strength: str = Field(
        default="",
        description="How strongly people self-identify with this group",
    )
    community_language: str = Field(
        default="",
        description="In-group phrases, vocabulary, jokes, or shared memes",
    )
    merchandise_potential: str = Field(
        description="Analysis of commercial merchandise potential (apparel, mugs, prints, gifts)",
    )
    target_audience_appeal: str = Field(
        description="Key emotional drivers, shared rituals, or cultural tensions",
    )
    selection_reason: str = Field(
        description="Provider rationale for prioritizing this seed for discovery",
    )


class Stage1ReasoningOutput(BaseModel):
    """Structured response model for Stage 1 provider evaluation."""

    executive_summary: str = Field(
        description="Provider executive summary of the selected seed portfolio",
    )
    evaluations: list[SeedAnalysis]


class SeedDiscoveryOutput(BaseModel):
    """Selected seed records, selection reasons, and structured OpenAI evaluations."""

    selected_seeds: list[SeedItem]
    selection_seed: int
    selection_reasons: dict[str, str]
    evaluations: list[dict] = Field(default_factory=list)
    executive_summary: str = ""
    model: str = "deterministic"


def select_candidate_seeds(input_data: SeedDiscoveryInput, seeds: list[SeedItem]) -> list[SeedItem]:
    """Select a balanced sample using only the supplied seed as random state.

    The three categories receive as-even-as-possible quotas. Shuffling each category separately
    prevents a large category from crowding out the others, and using a local RNG avoids changing
    unrelated application randomness or making concurrent runs influence one another.
    """

    if not seeds:
        raise ValueError("Seed discovery requires at least one seed record.")

    categories = tuple(SeedCategory)
    base_quota, remainder = divmod(input_data.max_seed_items, len(categories))
    quotas = {
        category: base_quota + (1 if index < remainder else 0)
        for index, category in enumerate(categories)
    }
    by_category = {category: [] for category in categories}
    for seed in seeds:
        by_category[seed.category].append(seed)

    for category, quota in quotas.items():
        if len(by_category[category]) < quota:
            raise ValueError(
                f"Seed discovery needs {quota} '{category.value}' records, "
                f"but only found {len(by_category[category])}."
            )

    rng = random.Random(input_data.selection_seed)
    selected: list[SeedItem] = []
    for category in categories:
        candidates = by_category[category].copy()
        rng.shuffle(candidates)
        selected.extend(candidates[: quotas[category]])
    return selected


def execute(
    input_data: SeedDiscoveryInput,
    seeds: list[SeedItem],
    reasoning_output: Stage1ReasoningOutput | None = None,
    model: str = "deterministic",
) -> SeedDiscoveryOutput:
    """Select reproducible seeds and attach optional provider evaluations to that sample."""

    selected = select_candidate_seeds(input_data, seeds)

    if reasoning_output is not None:
        eval_by_id = {item.seed_id: item for item in reasoning_output.evaluations}
        reasons = {
            seed.seed_id: (
                eval_by_id[seed.seed_id].selection_reason
                if seed.seed_id in eval_by_id
                else f"Selected from {input_data.seed_source} with priority {seed.metadata.get('priority', 0)}."
            )
            for seed in selected
        }
        eval_dicts = [item.model_dump() for item in reasoning_output.evaluations]
        return SeedDiscoveryOutput(
            selected_seeds=selected,
            selection_seed=input_data.selection_seed,
            selection_reasons=reasons,
            evaluations=eval_dicts,
            executive_summary=reasoning_output.executive_summary,
            model=model,
        )

    reasons = {
        seed.seed_id: (
            f"Selected from {input_data.seed_source} using selection seed "
            f"{input_data.selection_seed}."
        )
        for seed in selected
    }
    summary = (
        f"Selected {len(selected)} category-balanced seed groups from {input_data.seed_source} "
        f"using selection seed {input_data.selection_seed}."
    )
    return SeedDiscoveryOutput(
        selected_seeds=selected,
        selection_seed=input_data.selection_seed,
        selection_reasons=reasons,
        executive_summary=summary,
        model=model,
    )
