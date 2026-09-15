"""Stage 8: combine qualitative and deterministic signals into an opportunity score.

AI supplies bounded qualitative judgments for clarity, audience fit, and differentiation. The
application still owns evidence strength and the weighted total, so a provider cannot invent
research volume or silently change the scoring equation. The deterministic formula remains the
fallback and provides a reproducible baseline for fixture mode and provider failures.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import Niche
from merchandise_discovery.domain.stages.stage_07_experience_mining import ExperienceSignal


class OpportunityScoreInput(BaseModel):
    """Niches and mined signals used by the reproducible scoring formula."""

    niches: list[Niche]
    signals: list[ExperienceSignal]


class OpportunityEvaluation(BaseModel):
    """Provider judgment for the qualitative components of one niche's score."""

    niche_id: str = Field(min_length=1)
    experience_clarity: float = Field(ge=0, le=30)
    audience_fit: float = Field(ge=0, le=20)
    differentiation: float = Field(ge=0, le=20)
    rationale: str = Field(min_length=1, max_length=500)


class Stage8ReasoningOutput(BaseModel):
    """Exact structured response expected from OpenAI for Stage 8."""

    evaluations: list[OpportunityEvaluation] = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=500)


class OpportunityScore(BaseModel):
    """Component scores and final score for one researched niche."""

    niche_id: str
    evidence_strength: float = Field(ge=0, le=30)
    experience_clarity: float = Field(ge=0, le=30)
    audience_fit: float = Field(ge=0, le=20)
    differentiation: float = Field(ge=0, le=20)
    overall_score: float = Field(ge=0, le=100)
    rationale: str


class OpportunityScoringOutput(BaseModel):
    """Updated niche records plus their inspectable score breakdowns."""

    niches: list[Niche]
    scores: list[OpportunityScore]
    summary: str = ""
    model: str = "deterministic"


def _score_niche(
    niche: Niche,
    signal: ExperienceSignal | None,
    evaluation: OpportunityEvaluation | None = None,
) -> OpportunityScore:
    """Apply system-owned evidence scoring and optional bounded AI judgments."""

    evidence_count = min(niche.evidence_count, 3)
    evidence_strength = float(evidence_count * 10)
    signal_count = 0 if signal is None else sum(
        len(group)
        for group in (
            signal.repeated_language,
            signal.frustrations,
            signal.rituals,
            signal.emotional_signals,
        )
    )
    experience_clarity = float(min(30, signal_count * 5))
    audience_fit = round((signal.confidence if signal else 0) * 20, 2)
    differentiation = round(min(20, (niche.coherence_score or 0) * 2), 2)
    if evaluation is not None:
        experience_clarity = round(evaluation.experience_clarity, 2)
        audience_fit = round(evaluation.audience_fit, 2)
        differentiation = round(evaluation.differentiation, 2)
    overall = round(evidence_strength + experience_clarity + audience_fit + differentiation, 2)
    rationale = evaluation.rationale if evaluation is not None else (
        f"{evidence_count} evidence records, {signal_count} recurring signals, "
        f"and coherence {niche.coherence_score or 0:.2f}/10 produced the score."
    )
    return OpportunityScore(
        niche_id=niche.niche_id,
        evidence_strength=evidence_strength,
        experience_clarity=experience_clarity,
        audience_fit=audience_fit,
        differentiation=differentiation,
        overall_score=overall,
        rationale=rationale,
    )


def _validate_provider_links(
    input_data: OpportunityScoreInput,
    reasoning_output: Stage8ReasoningOutput,
) -> dict[str, OpportunityEvaluation]:
    """Ensure the provider evaluated exactly the niches supplied by Stage 6 and Stage 7."""

    expected_ids = {niche.niche_id for niche in input_data.niches}
    returned_ids = [evaluation.niche_id for evaluation in reasoning_output.evaluations]
    if len(returned_ids) != len(set(returned_ids)):
        raise ValueError("Stage 8 provider output contains duplicate niche IDs.")
    returned_id_set = set(returned_ids)
    unknown_ids = returned_id_set - expected_ids
    missing_ids = expected_ids - returned_id_set
    if unknown_ids:
        raise ValueError(f"Stage 8 provider output contains unknown niche IDs: {sorted(unknown_ids)}.")
    if missing_ids:
        raise ValueError(f"Stage 8 provider output is missing niche IDs: {sorted(missing_ids)}.")
    return {evaluation.niche_id: evaluation for evaluation in reasoning_output.evaluations}


def execute(
    input_data: OpportunityScoreInput,
    reasoning_output: Stage8ReasoningOutput | None = None,
    model: str = "deterministic",
) -> OpportunityScoringOutput:
    """Score every niche and attach its mined experience summary."""

    signals_by_niche = {signal.niche_id: signal for signal in input_data.signals}
    evaluations_by_niche = (
        _validate_provider_links(input_data, reasoning_output)
        if reasoning_output is not None
        else {}
    )
    scores: list[OpportunityScore] = []
    niches: list[Niche] = []
    for niche in input_data.niches:
        signal = signals_by_niche.get(niche.niche_id)
        score = _score_niche(niche, signal, evaluations_by_niche.get(niche.niche_id))
        scores.append(score)
        niches.append(
            niche.model_copy(
                update={
                    "experience_summary": signal.experience_summary if signal else None,
                    "opportunity_score": score.overall_score,
                    "validated": niche.validated and bool(signal and signal.evidence_ids),
                }
            )
        )
    niches.sort(key=lambda item: (-(item.opportunity_score or 0), item.niche_id))
    scores.sort(key=lambda item: (-item.overall_score, item.niche_id))
    return OpportunityScoringOutput(
        niches=niches,
        scores=scores,
        summary=reasoning_output.summary if reasoning_output is not None else "",
        model=model,
    )
