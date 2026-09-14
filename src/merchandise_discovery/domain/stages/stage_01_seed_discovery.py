"""Stage 1: select promising broad identity groups from seed knowledge.

This stage is deterministic for the MVP. It ranks validated seed records by configured priority and
records a reason for every selection so later provider-backed ranking has a reproducible baseline.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import SeedItem
from merchandise_discovery.domain.models.common import SeedCategory


class SeedDiscoveryInput(BaseModel):
    """Configuration needed to select a bounded seed set."""

    seed_source: str = "mvp_seed_library"
    max_seed_items: int = Field(default=12, ge=1, le=100)


class SeedAnalysis(BaseModel):
    """Structured evaluation of a candidate seed from Luna reasoning."""

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
        description="Luna's strategic rationale for prioritizing this seed for discovery",
    )


class Stage1ReasoningOutput(BaseModel):
    """Structured response model for Luna Stage 1 seed discovery evaluation."""

    executive_summary: str = Field(
        description="Luna's strategic executive summary of the selected seed portfolio",
    )
    evaluations: list[SeedAnalysis]


class SeedDiscoveryOutput(BaseModel):
    """Selected seed records, selection reasons, and structured OpenAI evaluations."""

    selected_seeds: list[SeedItem]
    selection_reasons: dict[str, str]
    evaluations: list[dict] = Field(default_factory=list)
    executive_summary: str = ""
    model: str = "deterministic"


def select_candidate_seeds(input_data: SeedDiscoveryInput, seeds: list[SeedItem]) -> list[SeedItem]:
    """Deterministically order and bound candidate seeds by configured priority and tie-breakers."""

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
    return ordered[: input_data.max_seed_items]


def execute(
    input_data: SeedDiscoveryInput,
    seeds: list[SeedItem],
    reasoning_output: Stage1ReasoningOutput | None = None,
    model: str = "deterministic",
) -> SeedDiscoveryOutput:
    """Select highest-priority seeds with deterministic ordering and optional provider evaluation."""

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
            selection_reasons=reasons,
            evaluations=eval_dicts,
            executive_summary=reasoning_output.executive_summary,
            model=model,
        )

    reasons = {
        seed.seed_id: (
            f"Selected from {input_data.seed_source} with priority "
            f"{seed.metadata.get('priority', 0)}."
        )
        for seed in selected
    }
    summary = (
        f"Selected {len(selected)} high-priority seed groups from {input_data.seed_source} "
        f"based on configured priority rankings."
    )
    return SeedDiscoveryOutput(
        selected_seeds=selected,
        selection_reasons=reasons,
        executive_summary=summary,
        model=model,
    )
