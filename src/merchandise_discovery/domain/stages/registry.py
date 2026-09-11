"""Stable stage metadata used to initialize and render workflow executions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StageDefinition:
    """Static metadata for one stage; runtime state belongs in MongoDB."""

    number: int
    name: str
    optional: bool = False


STAGE_DEFINITIONS: tuple[StageDefinition, ...] = (
    StageDefinition(1, "Autonomous Seed Discovery"),
    StageDefinition(2, "Identity Universe Expansion"),
    StageDefinition(3, "Intersection Generation"),
    StageDefinition(4, "Coherence and Experience Hypothesis"),
    StageDefinition(5, "Pre-Research Filter"),
    StageDefinition(6, "Niche Research and Validation"),
    StageDefinition(7, "Experience Mining"),
    StageDefinition(8, "Niche Opportunity Scoring"),
    StageDefinition(9, "Merchandise Concept Generation"),
    StageDefinition(10, "Single-Call Concept Critique"),
    StageDefinition(11, "Similarity and IP Check", optional=True),
    StageDefinition(12, "Final Concept Selection"),
    StageDefinition(13, "Structured Design Brief"),
    StageDefinition(14, "Grok Prompt Compilation"),
    StageDefinition(15, "Merchandise Artwork Generation"),
    StageDefinition(16, "Single-Call Artwork Critique"),
    StageDefinition(17, "Human Approval"),
)

