"""Stage 14: compile deterministic, policy-complete prompts from design briefs."""

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
    summary: str = ""


def _compile(brief: DesignBrief) -> str:
    """Apply brief-specific instructions plus permanent merchandise safety/layout rules."""

    constraints = "; ".join(brief.constraints + brief.things_to_avoid)
    return (
        "Create merchandise artwork only, not a product mockup. "
        "Use an isolated, print-ready composition with no unnecessary background scene. "
        "Use a square 1:1 aspect ratio unless the brief explicitly requests another ratio. "
        f'Exact text: "{brief.exact_phrase}". '
        f"Target audience: {brief.target_audience}. "
        f"Core concept: {brief.core_concept}. "
        f"Emotional idea: {brief.emotional_idea}. "
        f"Main subject: {brief.main_subject}. "
        f"Supporting elements: {', '.join(brief.supporting_elements)}. "
        f"Style: {brief.illustration_style}. "
        f"Composition: {brief.composition}. "
        f"Typography: {brief.typography_direction}. "
        f"Palette: {brief.palette_direction}. "
        f"Detail level: {brief.detail_level}. "
        f"Intended merchandise: {brief.intended_merchandise_type}. "
        f"Visual constraints and avoid list: {constraints}. "
        "Permanent rules: no extra text, no logos or brand marks, no product mockup unless "
        "explicitly requested, no unnecessary scene, preserve exact spelling, and keep the "
        "design legible at merchandise scale."
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
        ],
        summary="Compiled prompts with deterministic brief and permanent merchandise rules.",
    )
