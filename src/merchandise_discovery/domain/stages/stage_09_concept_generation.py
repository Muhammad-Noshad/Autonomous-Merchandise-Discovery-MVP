"""Stage 9: generate merchandise concepts from validated experiences.

The MVP uses transparent experience-led templates. They are intentionally isolated from the future
reasoning provider so the client can inspect the funnel before any model call is introduced.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import MerchandiseConcept, Niche


class ConceptGenerationInput(BaseModel):
    """Validated niches and the configured number of concepts per niche."""

    niches: list[Niche]
    concepts_per_niche: int = Field(ge=1, le=50)


class ConceptGenerationOutput(BaseModel):
    """Generated concept candidates before critique."""

    concepts: list[MerchandiseConcept]


CONCEPT_TEMPLATES = (
    ("Reset Mode", "A compact visual idea about finding a reset after a demanding day."),
    ("Small Ritual Energy", "A warm, specific idea centered on the repeatable ritual that restores energy."),
    ("Make Room to Unwind", "An experience-led phrase that makes decompression feel visible and shared."),
    ("Specific Humor, Shared Relief", "A humorous concept for people who recognize the same relief ritual."),
    ("Visible Belonging", "A community-minded concept that turns a private experience into a signal of belonging."),
)


def execute(input_data: ConceptGenerationInput) -> ConceptGenerationOutput:
    """Create bounded candidates only for validated niches with an evidence-backed experience."""

    concepts: list[MerchandiseConcept] = []
    for niche in input_data.niches:
        if not niche.validated or not niche.experience_summary:
            continue
        for index in range(input_data.concepts_per_niche):
            template_phrase, template_description = CONCEPT_TEMPLATES[index % len(CONCEPT_TEMPLATES)]
            concepts.append(
                MerchandiseConcept(
                    run_id=niche.run_id,
                    niche_id=niche.niche_id,
                    phrase=template_phrase,
                    description=(
                        f"{template_description} It is grounded in the observed experience: "
                        f"{niche.experience_summary}"
                    ),
                )
            )
    return ConceptGenerationOutput(concepts=concepts)
