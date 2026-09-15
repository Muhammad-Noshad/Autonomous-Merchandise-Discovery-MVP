"""Stage 9: generate merchandise concepts from validated experiences.

The provider contract contains proposals only. Application-owned concept IDs, run IDs, and niche
eligibility are applied after strict validation, so an AI response cannot create orphaned records or
generate concepts for a niche that failed research validation. Transparent templates remain the
deterministic path when fixture mode is selected.
"""

import re

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import MerchandiseConcept, Niche


class ConceptGenerationInput(BaseModel):
    """Validated niches and the configured number of concepts per niche."""

    niches: list[Niche]
    concepts_per_niche: int = Field(ge=1, le=50)


class ConceptProposal(BaseModel):
    """Provider proposal without persistence-owned identifiers."""

    niche_id: str = Field(min_length=1)
    phrase: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=600)


class Stage9ReasoningOutput(BaseModel):
    """Exact structured response expected from OpenAI for Stage 9."""

    concepts: list[ConceptProposal] = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=500)


class ConceptGenerationOutput(BaseModel):
    """Generated concept candidates before critique."""

    concepts: list[MerchandiseConcept]
    summary: str = ""
    model: str = "deterministic"


CONCEPT_TEMPLATES = (
    ("Reset Mode", "A compact visual idea about finding a reset after a demanding day."),
    ("Small Ritual Energy", "A warm, specific idea centered on the repeatable ritual that restores energy."),
    ("Make Room to Unwind", "An experience-led phrase that makes decompression feel visible and shared."),
    ("Specific Humor, Shared Relief", "A humorous concept for people who recognize the same relief ritual."),
    ("Visible Belonging", "A community-minded concept that turns a private experience into a signal of belonging."),
)


def _normalized_phrase(phrase: str) -> str:
    """Normalize whitespace and case for duplicate proposals within one niche."""

    return re.sub(r"\s+", " ", phrase.casefold()).strip()


def _validated_niches(input_data: ConceptGenerationInput) -> dict[str, Niche]:
    """Return only niches that passed research and have an experience summary."""

    return {
        niche.niche_id: niche
        for niche in input_data.niches
        if niche.validated and bool(niche.experience_summary)
    }


def _validate_provider_links(
    input_data: ConceptGenerationInput,
    reasoning_output: Stage9ReasoningOutput,
) -> dict[str, list[ConceptProposal]]:
    """Validate niche ownership, per-niche bounds, and duplicate provider proposals."""

    allowed_niches = _validated_niches(input_data)
    proposals_by_niche: dict[str, list[ConceptProposal]] = {niche_id: [] for niche_id in allowed_niches}
    for proposal in reasoning_output.concepts:
        if proposal.niche_id not in allowed_niches:
            raise ValueError(
                f"Stage 9 provider output contains a non-validated or unknown niche ID: "
                f"{proposal.niche_id}."
            )
        proposals_by_niche[proposal.niche_id].append(proposal)

    missing_niches = [niche_id for niche_id, proposals in proposals_by_niche.items() if not proposals]
    if missing_niches:
        raise ValueError(f"Stage 9 provider output is missing concepts for niches: {missing_niches}.")
    for niche_id, proposals in proposals_by_niche.items():
        if len(proposals) > input_data.concepts_per_niche:
            raise ValueError(
                f"Stage 9 provider output exceeds concepts_per_niche for niche {niche_id}."
            )
        normalized_phrases = [_normalized_phrase(proposal.phrase) for proposal in proposals]
        if len(normalized_phrases) != len(set(normalized_phrases)):
            raise ValueError(f"Stage 9 provider output contains duplicate phrases for niche {niche_id}.")
    return proposals_by_niche


def execute(
    input_data: ConceptGenerationInput,
    reasoning_output: Stage9ReasoningOutput | None = None,
    model: str = "deterministic",
) -> ConceptGenerationOutput:
    """Create local concept records from validated provider proposals or templates."""

    concepts: list[MerchandiseConcept] = []
    validated_niches = _validated_niches(input_data)
    if reasoning_output is not None:
        proposals_by_niche = _validate_provider_links(input_data, reasoning_output)
        # IDs are generated here, after validation, so the provider cannot collide with another
        # run or attach a critique to an arbitrary persisted concept.
        for niche_id, proposals in proposals_by_niche.items():
            niche = validated_niches[niche_id]
            concepts.extend(
                MerchandiseConcept(
                    run_id=niche.run_id,
                    niche_id=niche.niche_id,
                    phrase=proposal.phrase.strip(),
                    description=proposal.description.strip(),
                )
                for proposal in proposals
            )
        return ConceptGenerationOutput(
            concepts=concepts,
            summary=reasoning_output.summary,
            model=model,
        )

    for niche in validated_niches.values():
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
    return ConceptGenerationOutput(concepts=concepts, model=model)
