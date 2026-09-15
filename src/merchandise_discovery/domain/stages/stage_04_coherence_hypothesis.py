"""Stage 4: use structured reasoning to validate intersection coherence.

Stage 3 proposes combinations. This module owns the typed Stage 4 response contract and the local
trust boundary that maps provider evaluations back onto application-owned intersection records.
The deterministic scorer remains available as a safe fallback when live reasoning is unavailable.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import IdentityIntersection


class CoherenceInput(BaseModel):
    """Intersections awaiting experience coherence evaluation."""

    intersections: list[IdentityIntersection]


class CoherenceEvaluation(BaseModel):
    """One structured model judgment for a supplied intersection."""

    intersection_id: str = Field(min_length=1)
    coherence_score: float = Field(ge=0, le=10)
    experience_hypothesis: str = Field(min_length=1, max_length=500)
    shared_signals: list[str] = Field(min_length=1, max_length=12)
    coherence_rationale: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class Stage4ReasoningOutput(BaseModel):
    """Exact structured response expected from OpenAI for Stage 4."""

    evaluations: list[CoherenceEvaluation] = Field(min_length=1, max_length=50)
    summary: str = Field(min_length=1, max_length=500)


class CoherenceOutput(BaseModel):
    """Intersections enriched with validated hypotheses and coherence scores."""

    intersections: list[IdentityIntersection]
    provider_evaluations_count: int = Field(default=0, ge=0)
    summary: str = ""
    model: str = "deterministic"


_HYPOTHESIS_TEMPLATES = {
    "care": "A care-heavy audience may use this combination to express responsibility with warmth.",
    "decompression": "This combination points to a recognizable ritual for decompressing after pressure.",
    "focus": "This combination may express the tension between protecting focus and staying connected.",
    "humor": "This combination creates room for an inside joke about a familiar everyday struggle.",
    "ritual": "This combination centers on a repeatable ritual that makes small progress visible.",
}


def _apply_provider_evaluations(
    intersections: list[IdentityIntersection],
    reasoning_output: Stage4ReasoningOutput,
    *,
    model: str,
) -> CoherenceOutput:
    """Validate complete ID coverage and merge model judgments onto trusted records."""

    expected_ids = {item.intersection_id for item in intersections}
    evaluations = reasoning_output.evaluations
    evaluation_ids = [item.intersection_id for item in evaluations]
    if len(evaluation_ids) != len(set(evaluation_ids)):
        raise ValueError("Stage 4 provider output contains duplicate intersection IDs.")
    if set(evaluation_ids) != expected_ids:
        missing = sorted(expected_ids - set(evaluation_ids))
        unknown = sorted(set(evaluation_ids) - expected_ids)
        raise ValueError(
            f"Stage 4 provider output must cover every supplied intersection; "
            f"missing={missing}, unknown={unknown}."
        )

    by_id = {item.intersection_id: item for item in evaluations}
    enriched = []
    for intersection in intersections:
        evaluation = by_id[intersection.intersection_id]
        enriched.append(
            intersection.model_copy(
                update={
                    "coherence_score": round(evaluation.coherence_score, 2),
                    "experience_hypotheses": [evaluation.experience_hypothesis],
                    "metadata": {
                        **intersection.metadata,
                        "coherence_shared_signals": evaluation.shared_signals,
                        "coherence_rationale": evaluation.coherence_rationale,
                        "coherence_confidence": evaluation.confidence,
                        "coherence_generation_method": "provider",
                        "coherence_model": model,
                    },
                }
            )
        )
    return CoherenceOutput(
        intersections=enriched,
        provider_evaluations_count=len(evaluations),
        summary=reasoning_output.summary,
        model=model,
    )


def _apply_deterministic_scoring(intersections: list[IdentityIntersection]) -> CoherenceOutput:
    """Provide a reproducible local result when the live provider cannot be used."""

    scored: list[IdentityIntersection] = []
    for intersection in intersections:
        tags = [str(tag) for tag in intersection.metadata.get("shared_tags", [])]
        primary_tag = tags[0] if tags else ""
        score = min(
            10.0,
            4.0 + len(tags) * 1.25 + (0.75 if len(intersection.identities) == 3 else 0),
        )
        hypothesis = _HYPOTHESIS_TEMPLATES.get(
            primary_tag,
            "This combination needs stronger shared signals before it is ready for research.",
        )
        scored.append(
            intersection.model_copy(
                update={
                    "coherence_score": round(score, 2),
                    "experience_hypotheses": [hypothesis],
                    "metadata": {
                        **intersection.metadata,
                        "coherence_rationale": (
                            f"{len(tags)} shared affinity tag(s); "
                            f"{len(intersection.identities)} identity dimensions."
                        ),
                        "coherence_generation_method": "deterministic",
                        "coherence_model": "deterministic",
                    },
                }
            )
        )
    return CoherenceOutput(intersections=scored)


def execute(
    input_data: CoherenceInput,
    *,
    reasoning_output: Stage4ReasoningOutput | None = None,
    model: str = "deterministic",
) -> CoherenceOutput:
    """Apply provider judgments after validating them, or use the deterministic fallback."""

    if reasoning_output is not None:
        return _apply_provider_evaluations(input_data.intersections, reasoning_output, model=model)
    return _apply_deterministic_scoring(input_data.intersections)
