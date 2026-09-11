"""Stage 13: turn selected concepts into structured visual design briefs.

The brief is the boundary between merchandise reasoning and image generation. Keeping it typed
means prompt rules and artwork providers can evolve without changing concept selection.
"""

from pydantic import BaseModel

from merchandise_discovery.domain.models.artifacts import DesignBrief, MerchandiseConcept


class DesignBriefInput(BaseModel):
    """Finalist concepts that are ready for visual development."""

    concepts: list[MerchandiseConcept]


class DesignBriefOutput(BaseModel):
    """Structured briefs linked to their source concepts."""

    briefs: list[DesignBrief]


def execute(input_data: DesignBriefInput) -> DesignBriefOutput:
    """Create one constrained brief per selected concept."""

    briefs = [
        DesignBrief(
            run_id=concept.run_id,
            concept_id=concept.concept_id,
            target_audience="People sharing the researched experience",
            exact_phrase=concept.phrase,
            emotional_idea=concept.description,
            illustration_style="Clean editorial illustration with a warm, slightly playful tone",
            main_subject="A simple symbolic object representing a personal reset ritual",
            supporting_elements=["subtle motion cue", "small environmental detail"],
            composition="Centered subject with clear negative space around the phrase",
            typography_direction="Readable bold sans-serif lettering with strong hierarchy",
            palette_direction="Planet Opus-inspired deep neutrals with restrained violet accent",
            constraints=[
                "No logos or existing brand marks",
                "No photorealistic mockup",
                "Phrase must be spelled exactly",
                "Artwork must remain legible at merchandise scale",
            ],
        )
        for concept in input_data.concepts
        if concept.selected
    ]
    return DesignBriefOutput(briefs=briefs)
