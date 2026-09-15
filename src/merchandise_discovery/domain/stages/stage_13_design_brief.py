"""Stage 13: turn selected concepts into structured visual design briefs.

The brief is the boundary between merchandise reasoning and image generation. Keeping it typed
means prompt rules and artwork providers can evolve without changing concept selection.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import DesignBrief, MerchandiseConcept


class DesignBriefInput(BaseModel):
    """Finalist concepts that are ready for visual development."""

    concepts: list[MerchandiseConcept]


class DesignBriefOutput(BaseModel):
    """Structured briefs linked to their source concepts."""

    briefs: list[DesignBrief]
    summary: str = ""
    model: str = "deterministic"


class DesignBriefProposal(BaseModel):
    """Provider-owned content for one brief, linked only by the application-known concept ID."""

    concept_id: str = Field(min_length=1)
    target_audience: str = Field(min_length=1, max_length=500)
    core_concept: str = Field(min_length=1, max_length=800)
    exact_phrase: str = Field(min_length=1, max_length=200)
    emotional_idea: str = Field(min_length=1, max_length=800)
    illustration_style: str = Field(min_length=1, max_length=500)
    main_subject: str = Field(min_length=1, max_length=500)
    supporting_elements: list[str] = Field(max_length=20)
    composition: str = Field(min_length=1, max_length=800)
    typography_direction: str = Field(min_length=1, max_length=500)
    palette_direction: str = Field(min_length=1, max_length=500)
    detail_level: str = Field(min_length=1, max_length=100)
    intended_merchandise_type: str = Field(min_length=1, max_length=200)
    visual_constraints: list[str] = Field(max_length=30)
    things_to_avoid: list[str] = Field(max_length=30)


class Stage13ReasoningOutput(BaseModel):
    """Strict batch response for one complete brief per finalist concept."""

    briefs: list[DesignBriefProposal] = Field(min_length=1, max_length=50)
    summary: str = Field(min_length=1, max_length=500)


def execute(
    input_data: DesignBriefInput,
    *,
    reasoning_output: Stage13ReasoningOutput | None = None,
    model: str = "deterministic",
) -> DesignBriefOutput:
    """Validate provider lineage and materialize local brief IDs for every finalist."""

    concepts = [concept for concept in input_data.concepts if concept.selected]
    concepts_by_id = {concept.concept_id: concept for concept in concepts}
    if len(concepts_by_id) != len(concepts):
        raise ValueError("Stage 13 input contains duplicate or unselected concept IDs.")

    if reasoning_output is not None:
        proposals_by_id = {proposal.concept_id: proposal for proposal in reasoning_output.briefs}
        if len(proposals_by_id) != len(reasoning_output.briefs):
            raise ValueError("Stage 13 provider response contains duplicate concept IDs.")
        unknown = set(proposals_by_id) - set(concepts_by_id)
        missing = set(concepts_by_id) - set(proposals_by_id)
        if unknown:
            raise ValueError(f"Stage 13 provider response contains unknown concept IDs: {sorted(unknown)}")
        if missing:
            raise ValueError(f"Stage 13 provider response is missing concept IDs: {sorted(missing)}")
        briefs = []
        for concept in concepts:
            proposal = proposals_by_id[concept.concept_id]
            if proposal.exact_phrase != concept.phrase:
                raise ValueError(
                    f"Stage 13 changed exact phrase for concept {concept.concept_id}."
                )
            briefs.append(
                DesignBrief(
                    run_id=concept.run_id,
                    concept_id=concept.concept_id,
                    target_audience=proposal.target_audience,
                    core_concept=proposal.core_concept,
                    exact_phrase=concept.phrase,
                    emotional_idea=proposal.emotional_idea,
                    illustration_style=proposal.illustration_style,
                    main_subject=proposal.main_subject,
                    supporting_elements=proposal.supporting_elements,
                    composition=proposal.composition,
                    typography_direction=proposal.typography_direction,
                    palette_direction=proposal.palette_direction,
                    detail_level=proposal.detail_level,
                    intended_merchandise_type=proposal.intended_merchandise_type,
                    constraints=proposal.visual_constraints,
                    things_to_avoid=proposal.things_to_avoid,
                )
            )
        return DesignBriefOutput(
            briefs=briefs,
            summary=reasoning_output.summary,
            model=model,
        )

    briefs = [
        DesignBrief(
            run_id=concept.run_id,
            concept_id=concept.concept_id,
            target_audience="People sharing the researched experience",
            core_concept=concept.description,
            exact_phrase=concept.phrase,
            emotional_idea=concept.description,
            illustration_style="Clean editorial illustration with a warm, slightly playful tone",
            main_subject="A simple symbolic object representing a personal reset ritual",
            supporting_elements=["subtle motion cue", "small environmental detail"],
            composition="Centered subject with clear negative space around the phrase",
            typography_direction="Readable bold sans-serif lettering with strong hierarchy",
            palette_direction="Planet Opus-inspired deep neutrals with restrained violet accent",
            detail_level="Moderate detail with clean shapes that survive merchandise printing",
            intended_merchandise_type="T-shirt or sweatshirt print",
            things_to_avoid=[
                "unreadable micro-text",
                "brand logos or trademarks",
                "busy scenic backgrounds",
            ],
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
    return DesignBriefOutput(
        briefs=briefs,
        summary="Design briefs compiled deterministically from finalist concepts.",
        model=model,
    )
