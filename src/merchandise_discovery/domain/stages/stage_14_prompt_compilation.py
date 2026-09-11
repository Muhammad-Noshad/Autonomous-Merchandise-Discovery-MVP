"""Stage 14: compile a constrained merchandise prompt from each design brief."""

from pydantic import BaseModel

from merchandise_discovery.domain.models.artifacts import DesignBrief


class PromptCompilation(BaseModel):
    """One compiled prompt linked to the brief and concept that produced it."""

    run_id: str
    concept_id: str
    brief_id: str
    prompt: str


class PromptCompilationInput(BaseModel):
    """Design briefs awaiting deterministic prompt compilation."""

    briefs: list[DesignBrief]


class PromptCompilationOutput(BaseModel):
    """Compiled prompts passed to the image-generation stage."""

    prompts: list[PromptCompilation]


def _compile(brief: DesignBrief) -> str:
    """Apply the same phrase, readability, and merchandise constraints to every brief."""

    constraints = "; ".join(brief.constraints)
    return (
        "Create a print-ready merchandise artwork. "
        f'Exact text: "{brief.exact_phrase}". '
        f"Audience and emotional idea: {brief.emotional_idea} "
        f"Main subject: {brief.main_subject}. "
        f"Style: {brief.illustration_style}. "
        f"Composition: {brief.composition}. "
        f"Typography: {brief.typography_direction}. "
        f"Palette: {brief.palette_direction}. "
        f"Constraints: {constraints}. "
        "Transparent or clean background, no extra text, no logos."
    )


def execute(input_data: PromptCompilationInput) -> PromptCompilationOutput:
    """Compile one reproducible prompt for each finalist brief."""

    return PromptCompilationOutput(
        prompts=[
            PromptCompilation(
                run_id=brief.run_id,
                concept_id=brief.concept_id,
                brief_id=brief.brief_id,
                prompt=_compile(brief),
            )
            for brief in input_data.briefs
        ]
    )
