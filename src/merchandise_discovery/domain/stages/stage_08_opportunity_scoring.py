"""Stage 8: combine qualitative and deterministic signals into an opportunity score.

Scoring is deliberately explicit for the MVP. The input snapshot, component weights, and rounded
result are persisted by the worker, allowing a score to be reproduced without replaying research.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import Niche
from merchandise_discovery.domain.stages.stage_07_experience_mining import ExperienceSignal


class OpportunityScoreInput(BaseModel):
    """Niches and mined signals used by the reproducible scoring formula."""

    niches: list[Niche]
    signals: list[ExperienceSignal]


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


def _score_niche(niche: Niche, signal: ExperienceSignal | None) -> OpportunityScore:
    """Apply bounded, documented weights to persisted research facts."""

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
    overall = round(evidence_strength + experience_clarity + audience_fit + differentiation, 2)
    rationale = (
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


def execute(input_data: OpportunityScoreInput) -> OpportunityScoringOutput:
    """Score every researched niche and attach its mined experience summary."""

    signals_by_niche = {signal.niche_id: signal for signal in input_data.signals}
    scores: list[OpportunityScore] = []
    niches: list[Niche] = []
    for niche in input_data.niches:
        signal = signals_by_niche.get(niche.niche_id)
        score = _score_niche(niche, signal)
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
    return OpportunityScoringOutput(niches=niches, scores=scores)
