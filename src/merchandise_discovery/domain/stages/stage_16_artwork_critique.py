"""Stage 16: have Luna critique each artwork against its specific merchandise context.

Live execution supplies the artwork image, its generation prompt, and its combination name to a
vision-capable reasoning provider. This module owns the provider-neutral structured contract and
the small amount of lineage validation needed before the next stage can edit flagged artwork.
Fixture execution retains the previous metadata checks so offline runs remain deterministic.
"""

from typing import Literal

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import Artwork
from merchandise_discovery.domain.models.common import ArtworkDecision


class ArtworkCritiqueInput(BaseModel):
    """Artwork candidates and their original prompts awaiting visual review."""

    artworks: list[Artwork]


class ArtworkEvaluation(BaseModel):
    """Persisted visual review and, when needed, the one-shot Grok edit instruction."""

    artwork_id: str
    readability: float = Field(ge=0, le=10)
    composition: float = Field(ge=0, le=10)
    quality: float = Field(ge=0, le=10)
    alignment: float = Field(ge=0, le=10)
    specificity: float = Field(default=0, ge=0, le=10)
    checks: dict[str, bool]
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    rationale: str = ""
    edit_prompt: str | None = None
    decision: ArtworkDecision


class ArtworkCritiqueOutput(BaseModel):
    """Artwork records and all structured evaluations retained for audit and revision."""

    artworks: list[Artwork]
    evaluations: list[ArtworkEvaluation]


class ArtworkCritiqueProposal(BaseModel):
    """Exact structured response expected from Luna for one image attachment."""

    artwork_id: str
    audience_relevance_score: float = Field(ge=0, le=10)
    niche_specificity_score: float = Field(ge=0, le=10)
    text_quality_score: float = Field(ge=0, le=10)
    composition_score: float = Field(ge=0, le=10)
    print_suitability_score: float = Field(ge=0, le=10)
    strengths: list[str] = Field(default_factory=list, max_length=8)
    issues: list[str] = Field(default_factory=list, max_length=12)
    rationale: str = Field(min_length=1, max_length=2_000)
    # One explicit outcome keeps the final gallery honest: rejected work must remain visible as
    # rejected, while only candidates needing a targeted Grok correction enter Stage 17.
    outcome: Literal["accepted", "regenerate", "rejected"]
    edit_prompt: str | None = Field(default=None, max_length=4_000)


def reasoning_instructions() -> str:
    """Return the high-signal review rubric used by the executor's multimodal request."""

    return (
        "Review the supplied artwork image against the exact generation prompt and combination. "
        "Judge whether the target audience would recognize their own specific lived experience, "
        "not merely the broad category. Inspect the wording in the image, visual specificity, "
        "composition, and print suitability. Return separate scores for audience relevance, niche "
        "specificity, text quality, composition, and print suitability, each from 0 to 10. Set outcome "
        "to exactly one of accepted, regenerate, or rejected. Use regenerate only when a concrete "
        "correction could make the image viable; use rejected when the concept should not continue. "
        "If outcome is regenerate, write one precise self-contained edit prompt for Grok that "
        "preserves successful parts and explicitly fixes the listed issues. For accepted or rejected, "
        "edit_prompt must be null. Do not suggest a second review and do not invent details absent "
        "from the supplied context."
    )


def _evaluate(artwork: Artwork) -> ArtworkEvaluation:
    """Run safe file and prompt checks before assigning an outcome."""

    checks = {
        "has_source_reference": bool(artwork.source_url or artwork.storage_key),
        "supported_mime_type": artwork.mime_type in {"image/png", "image/jpeg", "image/webp"},
        "minimum_dimensions": bool(
            artwork.width and artwork.height and artwork.width >= 512 and artwork.height >= 512
        ),
        "reasonable_file_size": bool(
            artwork.file_size_bytes and 1_000 <= artwork.file_size_bytes <= 10_000_000
        ),
        "square_merchandise_ratio": bool(
            artwork.width and artwork.height and abs(artwork.width / artwork.height - 1) <= 0.05
        ),
        "has_exact_text_instruction": "Exact text:" in artwork.prompt,
    }
    issues = [name.replace("_", " ").capitalize() for name, passed in checks.items() if not passed]
    passed = all(checks.values())
    decision = ArtworkDecision.ACCEPT if passed else ArtworkDecision.REGENERATE
    return ArtworkEvaluation(
        artwork_id=artwork.artwork_id,
        readability=9.0 if checks["has_exact_text_instruction"] else 4.0,
        composition=9.0 if checks["square_merchandise_ratio"] else 5.0,
        quality=9.0 if checks["supported_mime_type"] and checks["reasonable_file_size"] else 4.0,
        alignment=9.0 if checks["has_source_reference"] else 3.0,
        specificity=9.0 if checks["has_exact_text_instruction"] else 4.0,
        checks=checks,
        issues=issues,
        decision=decision,
    )


def _from_proposal(proposal: ArtworkCritiqueProposal) -> ArtworkEvaluation:
    """Convert one provider proposal into the durable evaluation contract."""

    if proposal.outcome == "regenerate" and not proposal.edit_prompt:
        raise ValueError(
            f"Artwork {proposal.artwork_id} requires an edit but Luna returned no edit prompt."
        )
    if proposal.outcome != "regenerate" and proposal.edit_prompt:
        raise ValueError(
            f"Artwork {proposal.artwork_id} returned an edit prompt for outcome {proposal.outcome}."
        )
    decision = {
        "accepted": ArtworkDecision.ACCEPT,
        "regenerate": ArtworkDecision.REGENERATE,
        "rejected": ArtworkDecision.REJECT,
    }[proposal.outcome]
    return ArtworkEvaluation(
        artwork_id=proposal.artwork_id,
        readability=proposal.text_quality_score,
        composition=proposal.composition_score,
        quality=proposal.print_suitability_score,
        alignment=proposal.audience_relevance_score,
        specificity=proposal.niche_specificity_score,
        checks={
            "luna_reviewed": True,
            "edit_instruction_valid": proposal.outcome != "regenerate" or bool(proposal.edit_prompt),
        },
        strengths=proposal.strengths,
        issues=proposal.issues,
        rationale=proposal.rationale,
        edit_prompt=proposal.edit_prompt,
        decision=decision,
    )


def execute(
    input_data: ArtworkCritiqueInput,
    reasoning_outputs: list[ArtworkCritiqueProposal] | None = None,
    *,
    model: str = "deterministic",
) -> ArtworkCritiqueOutput:
    """Attach either deterministic checks or complete Luna reviews to every artwork."""

    if reasoning_outputs is None:
        evaluations = [_evaluate(artwork) for artwork in input_data.artworks]
    else:
        expected_ids = [artwork.artwork_id for artwork in input_data.artworks]
        returned_ids = [proposal.artwork_id for proposal in reasoning_outputs]
        if len(returned_ids) != len(set(returned_ids)) or set(returned_ids) != set(expected_ids):
            raise ValueError("Luna artwork critique must return exactly one evaluation per artwork.")
        evaluations = [_from_proposal(proposal) for proposal in reasoning_outputs]
    by_id = {evaluation.artwork_id: evaluation for evaluation in evaluations}
    artworks = [
        artwork.model_copy(
            update={
                "decision": evaluation.decision,
                "critique": {
                    "readability": evaluation.readability,
                    "composition": evaluation.composition,
                    "quality": evaluation.quality,
                    "alignment": evaluation.alignment,
                    "specificity": evaluation.specificity,
                    "checks": evaluation.checks,
                    "strengths": evaluation.strengths,
                    "issues": evaluation.issues,
                    "rationale": evaluation.rationale,
                    "edit_prompt": evaluation.edit_prompt,
                    "review_model": model,
                },
            }
        )
        for artwork in input_data.artworks
        if (evaluation := by_id[artwork.artwork_id])
    ]
    return ArtworkCritiqueOutput(artworks=artworks, evaluations=evaluations)
