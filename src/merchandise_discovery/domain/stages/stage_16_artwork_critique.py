"""Stage 16: evaluate artwork quality and decide accept, reject, or regenerate.

The MVP can verify metadata and prompt constraints without computer vision. Visual quality fields
are therefore explicit fixture checks and remain separate from any future vision-model provider.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import Artwork
from merchandise_discovery.domain.models.common import ArtworkDecision


class ArtworkCritiqueInput(BaseModel):
    """Artwork candidates awaiting deterministic quality assurance."""

    artworks: list[Artwork]


class ArtworkEvaluation(BaseModel):
    """Quality checks, issues, and final QA decision for one artwork candidate."""

    artwork_id: str
    readability: float = Field(ge=0, le=10)
    composition: float = Field(ge=0, le=10)
    quality: float = Field(ge=0, le=10)
    alignment: float = Field(ge=0, le=10)
    checks: dict[str, bool]
    issues: list[str] = Field(default_factory=list)
    decision: ArtworkDecision


class ArtworkCritiqueOutput(BaseModel):
    """Artwork records updated with QA decisions and their inspectable evaluations."""

    artworks: list[Artwork]
    evaluations: list[ArtworkEvaluation]


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
        checks=checks,
        issues=issues,
        decision=decision,
    )


def execute(input_data: ArtworkCritiqueInput) -> ArtworkCritiqueOutput:
    """Attach QA decisions to every artwork candidate without hiding failed checks."""

    evaluations = [_evaluate(artwork) for artwork in input_data.artworks]
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
                    "checks": evaluation.checks,
                    "issues": evaluation.issues,
                },
            }
        )
        for artwork in input_data.artworks
        if (evaluation := by_id[artwork.artwork_id])
    ]
    return ArtworkCritiqueOutput(artworks=artworks, evaluations=evaluations)
