"""Stable stage metadata used to initialize and render workflow executions."""

from dataclasses import dataclass

from merchandise_discovery.domain.models.common import PipelineVariant


@dataclass(frozen=True)
class StageDefinition:
    """Static metadata for one stage; runtime state belongs in MongoDB."""

    number: int
    name: str
    purpose: str
    optional: bool = False
    version: str = "0.1.0"


STAGE_DEFINITIONS: tuple[StageDefinition, ...] = (
    StageDefinition(1, "Autonomous Seed Discovery", "Select high-value audience, interest, and value seeds to begin the funnel."),
    StageDefinition(2, "Identity Universe Expansion", "Expand each selected seed into core identities and contextual experience dimensions."),
    StageDefinition(3, "Intersection Generation", "Use AI to propose meaningful identity combinations, then validate and bound them with system rules."),
    StageDefinition(4, "AI Coherence and Research Selection", "Use structured AI reasoning to select only the most coherent, research-worthy intersections and explain each selection."),
    StageDefinition(5, "Research Selection Compatibility Pass", "Preserve the historical filter stage contract while passing through Stage 4's AI-selected research set."),
    StageDefinition(6, "Niche Research and Validation", "Collect public evidence to validate whether an intersection represents a real niche."),
    StageDefinition(7, "Experience Mining", "Extract repeated language, frustrations, rituals, and emotional signals from evidence."),
    StageDefinition(8, "Niche Opportunity Scoring", "Combine evidence strength and audience opportunity signals into a reproducible score."),
    StageDefinition(9, "Merchandise Concept Generation", "Translate validated experiences into specific, wearable merchandise concepts."),
    StageDefinition(10, "Single-Call Concept Critique", "Evaluate concept authenticity, clarity, wearability, and commercial potential."),
    StageDefinition(11, "Duplicate Phrase Screen", "Optionally identify duplicate merchandise phrases within this run.", optional=True),
    StageDefinition(12, "Final Concept Selection", "Rank surviving concepts and select the strongest finalists for visual development."),
    StageDefinition(13, "Structured Design Brief", "Convert each finalist into a detailed visual design brief."),
    StageDefinition(14, "Grok Prompt Compilation", "Compile a constrained image prompt from the design brief."),
    StageDefinition(15, "Merchandise Artwork Generation", "Generate a small set of artwork candidates for each finalist."),
    StageDefinition(16, "Single-Call Artwork Critique", "Check artwork readability, composition, quality, and concept alignment."),
    StageDefinition(17, "Human Approval", "Record the final reviewer decision and close the merchandise workflow."),
)


def stage_definitions_for(variant: PipelineVariant) -> tuple[StageDefinition, ...]:
    """Return the actual stage sequence for a selected pipeline variant."""

    if variant == PipelineVariant.BASELINE:
        return STAGE_DEFINITIONS
    return (
        *STAGE_DEFINITIONS[:5],
        StageDefinition(
            6,
            "AI Merchandise Development",
            "Search the selected niches, synthesize evidence, and generate concepts, briefs, and artwork prompts.",
        ),
        StageDefinition(7, "Merchandise Artwork Generation", "Generate artwork candidates from compact-stage prompts."),
        StageDefinition(8, "Artwork Critique", "Run deterministic artwork quality checks."),
        StageDefinition(9, "Human Approval", "Record the final reviewer decision and close the merchandise workflow."),
    )


def visible_stage_numbers(variant: PipelineVariant) -> set[int]:
    """Return stages that belong in the selected variant's client-facing pipeline view."""

    return {definition.number for definition in stage_definitions_for(variant)}
