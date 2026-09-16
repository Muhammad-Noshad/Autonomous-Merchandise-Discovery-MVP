"""Stage 9: generate specific merchandise concepts from validated experiences.

The provider contract contains proposals only. Application-owned concept IDs, run IDs, and niche
eligibility are applied after strict validation, so an AI response cannot create orphaned records or
generate concepts for a niche that failed research validation. Transparent templates remain the
deterministic path when fixture mode is selected.
"""

import re

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import MerchandiseConcept, Niche
from merchandise_discovery.domain.stages.stage_07_experience_mining import ExperienceSignal


class ConceptGenerationInput(BaseModel):
    """Validated niches plus evidence-linked signals needed for specific concept generation."""

    niches: list[Niche]
    experience_signals: list[ExperienceSignal] = Field(default_factory=list)
    concepts_per_niche: int = Field(ge=1, le=50)


class ConceptProposal(BaseModel):
    """Provider proposal containing the personal detail required for a useful concept."""

    niche_id: str = Field(min_length=1)
    phrase: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=600)
    specific_audience: str = Field(min_length=1, max_length=300)
    recognizable_moment: str = Field(min_length=1, max_length=500)
    insider_behavior_or_language: str = Field(min_length=1, max_length=300)
    emotional_tension: str = Field(min_length=1, max_length=300)
    visual_hook: str = Field(min_length=1, max_length=300)
    audience_identification_reason: str = Field(min_length=1, max_length=400)
    specificity_score: float = Field(
        ge=0,
        le=10,
        description=(
            "Specificity score from 0.0 to 10.0, where 10 is highly personal and experience-led. "
            "This is not a confidence or probability value from 0.0 to 1.0."
        ),
    )


class Stage9ReasoningOutput(BaseModel):
    """Exact structured response expected from OpenAI for Stage 9."""

    concepts: list[ConceptProposal] = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=500)


class ConceptRejection(BaseModel):
    """An AI proposal rejected by deterministic specificity policy before persistence."""

    niche_id: str
    phrase: str
    reason: str


class ConceptGenerationOutput(BaseModel):
    """Generated concept candidates before critique."""

    concepts: list[MerchandiseConcept]
    rejected_proposals: list[ConceptRejection] = Field(default_factory=list)
    provider_proposals_count: int = Field(default=0, ge=0)
    summary: str = ""
    model: str = "deterministic"


CONCEPT_TEMPLATES = (
    ("Reset Mode", "A compact visual idea about finding a reset after a demanding day."),
    ("Small Ritual Energy", "A warm, specific idea centered on the repeatable ritual that restores energy."),
    ("Make Room to Unwind", "An experience-led phrase that makes decompression feel visible and shared."),
    ("Specific Humor, Shared Relief", "A humorous concept for people who recognize the same relief ritual."),
    ("Visible Belonging", "A community-minded concept that turns a private experience into a signal of belonging."),
)

GENERIC_LABEL_SUFFIXES = {
    "adventures",
    "challenges",
    "club",
    "community",
    "experiences",
    "lifestyle",
    "solutions",
}


def reasoning_instructions() -> str:
    """Return the Stage 9-specific creative contract used by the provider adapter."""

    return (
        "Generate narrow, experience-led merchandise concepts, not category names, event "
        "descriptions, demographic summaries, or generic themes. Ground every concept in the "
        "supplied evidence-linked experience signals. Each concept must describe one specific "
        "audience, one recognizable moment or repeated behavior, one insider phrase or language "
        "cue, one emotional tension, and one distinctive visual hook. The merchandise phrase is the "
        "primary audience-recognition copy printed on the product: write it as an insider statement "
        "or shared truth that makes the target audience think, 'That is literally me.' Prefer first "
        "person or direct audience language and include the specific behavior, constraint, or relief "
        "that defines the niche. Do not return a product category, club name, campaign title, broad "
        "theme, or abstract slogan in place of the phrase. The phrase must work as standalone copy on "
        "a shirt or other product. Reject ideas that could apply equally to almost any audience. Do not "
        "invent demographics or facts absent from the supplied input. "
        "The specificity_score is a 0 to 10 score, not a 0 to 1 confidence value; use at least "
        "7.0 for a concept that should pass the application gate. Before returning, self-check "
        "that every supplied validated niche has at least one concept with a score of 7.0 or "
        "higher and that its phrase, moment, insider cue, emotional tension, and visual hook all "
        "refer to that niche's supplied evidence. Return no more than the configured concepts per "
        "niche and make the concepts meaningfully different from one another."
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
) -> tuple[dict[str, list[ConceptProposal]], list[ConceptRejection]]:
    """Validate ownership and retain only proposals that pass the specificity gate."""

    allowed_niches = _validated_niches(input_data)
    proposals_by_niche: dict[str, list[ConceptProposal]] = {niche_id: [] for niche_id in allowed_niches}
    rejected: list[ConceptRejection] = []
    for proposal in reasoning_output.concepts:
        if proposal.niche_id not in allowed_niches:
            raise ValueError(
                f"Stage 9 provider output contains a non-validated or unknown niche ID: "
                f"{proposal.niche_id}."
            )
        phrase_words = proposal.phrase.split()
        phrase_suffix = phrase_words[-1].casefold() if phrase_words else ""
        if phrase_suffix in GENERIC_LABEL_SUFFIXES:
            rejected.append(
                ConceptRejection(
                    niche_id=proposal.niche_id,
                    phrase=proposal.phrase,
                    reason="The phrase ends as a broad category label rather than a personal insight.",
                )
            )
        elif proposal.specificity_score < 7:
            rejected.append(
                ConceptRejection(
                    niche_id=proposal.niche_id,
                    phrase=proposal.phrase,
                    reason="The provider specificity score is below the minimum threshold of 7/10.",
                )
            )
        else:
            proposals_by_niche[proposal.niche_id].append(proposal)

    missing_niches = [niche_id for niche_id, proposals in proposals_by_niche.items() if not proposals]
    if missing_niches:
        rejection_reasons: dict[str, list[str]] = {niche_id: [] for niche_id in missing_niches}
        for item in rejected:
            if item.niche_id in rejection_reasons and len(rejection_reasons[item.niche_id]) < 3:
                rejection_reasons[item.niche_id].append(item.reason)
        details = "; ".join(
            f"{niche_id}: {', '.join(reasons) or 'no proposal returned'}"
            for niche_id, reasons in rejection_reasons.items()
        )
        raise ValueError(
            "Stage 9 provider output has no specificity-approved concept for niches: "
            f"{missing_niches}. Rejection details: {details}."
        )
    for niche_id, proposals in proposals_by_niche.items():
        if len(proposals) > input_data.concepts_per_niche:
            raise ValueError(
                f"Stage 9 provider output exceeds concepts_per_niche for niche {niche_id}."
            )
        normalized_phrases = [_normalized_phrase(proposal.phrase) for proposal in proposals]
        if len(normalized_phrases) != len(set(normalized_phrases)):
            raise ValueError(f"Stage 9 provider output contains duplicate phrases for niche {niche_id}.")
    return proposals_by_niche, rejected


def execute(
    input_data: ConceptGenerationInput,
    reasoning_output: Stage9ReasoningOutput | None = None,
    model: str = "deterministic",
) -> ConceptGenerationOutput:
    """Create local concept records from validated provider proposals or templates."""

    concepts: list[MerchandiseConcept] = []
    validated_niches = _validated_niches(input_data)
    if reasoning_output is not None:
        proposals_by_niche, rejected = _validate_provider_links(input_data, reasoning_output)
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
                    specific_audience=proposal.specific_audience.strip(),
                    recognizable_moment=proposal.recognizable_moment.strip(),
                    insider_behavior_or_language=proposal.insider_behavior_or_language.strip(),
                    emotional_tension=proposal.emotional_tension.strip(),
                    visual_hook=proposal.visual_hook.strip(),
                    audience_identification_reason=proposal.audience_identification_reason.strip(),
                    specificity_score=round(proposal.specificity_score, 2),
                )
                for proposal in proposals
            )
        return ConceptGenerationOutput(
            concepts=concepts,
            rejected_proposals=rejected,
            provider_proposals_count=len(reasoning_output.concepts),
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
                    specific_audience=niche.name,
                    recognizable_moment=niche.experience_summary or "A repeated moment from the researched experience.",
                    insider_behavior_or_language="The audience recognizes the same repeated pattern.",
                    emotional_tension="Wanting relief while still carrying the original demand.",
                    visual_hook="A single symbolic object representing the repeated ritual.",
                    audience_identification_reason="The concept names a shared lived experience rather than a broad demographic.",
                    specificity_score=7.0,
                )
            )
    return ConceptGenerationOutput(concepts=concepts, model=model)
