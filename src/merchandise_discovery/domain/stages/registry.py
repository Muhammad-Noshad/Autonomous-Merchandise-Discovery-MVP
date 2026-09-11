"""Stable stage metadata used to initialize and render workflow executions."""

from dataclasses import dataclass


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
    StageDefinition(3, "Intersection Generation", "Combine compatible identity categories into bounded candidate intersections."),
    StageDefinition(4, "Coherence and Experience Hypothesis", "Score shared signals and propose a recognizable experience hypothesis for each candidate."),
    StageDefinition(5, "Pre-Research Filter", "Remove duplicates and weak candidates before spending resources on external research."),
    StageDefinition(6, "Niche Research and Validation", "Collect public evidence to validate whether an intersection represents a real niche."),
    StageDefinition(7, "Experience Mining", "Extract repeated language, frustrations, rituals, and emotional signals from evidence."),
    StageDefinition(8, "Niche Opportunity Scoring", "Combine evidence strength and audience opportunity signals into a reproducible score."),
    StageDefinition(9, "Merchandise Concept Generation", "Translate validated experiences into specific, wearable merchandise concepts."),
    StageDefinition(10, "Single-Call Concept Critique", "Evaluate concept authenticity, clarity, wearability, and commercial potential."),
    StageDefinition(11, "Similarity and IP Check", "Optionally identify duplication and potential intellectual-property risks.", optional=True),
    StageDefinition(12, "Final Concept Selection", "Rank surviving concepts and select the strongest finalists for visual development."),
    StageDefinition(13, "Structured Design Brief", "Convert each finalist into a detailed visual design brief."),
    StageDefinition(14, "Grok Prompt Compilation", "Compile a constrained image prompt from the design brief."),
    StageDefinition(15, "Merchandise Artwork Generation", "Generate a small set of artwork candidates for each finalist."),
    StageDefinition(16, "Single-Call Artwork Critique", "Check artwork readability, composition, quality, and concept alignment."),
    StageDefinition(17, "Human Approval", "Record the final reviewer decision and close the merchandise workflow."),
)
