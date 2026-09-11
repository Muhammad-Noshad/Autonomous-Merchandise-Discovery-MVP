"""Stage 7: extract recurring audience experiences and language.

The MVP uses transparent keyword evidence mapping instead of an opaque model call. Each signal
retains the evidence IDs that supported it, so a reviewer can distinguish observed language from a
future interpretation layer.
"""

from collections import defaultdict

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import Niche, ResearchEvidence


class ExperienceMiningInput(BaseModel):
    """Researched niches and their source-backed observations."""

    niches: list[Niche]
    evidence: list[ResearchEvidence]


class ExperienceSignal(BaseModel):
    """Evidence-linked recurring experience signals for one niche."""

    niche_id: str
    repeated_language: list[str] = Field(default_factory=list)
    frustrations: list[str] = Field(default_factory=list)
    rituals: list[str] = Field(default_factory=list)
    emotional_signals: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    experience_summary: str


class ExperienceMiningOutput(BaseModel):
    """All mined signals, retaining a one-to-many link back to stored evidence."""

    signals: list[ExperienceSignal]


SIGNAL_RULES: dict[str, tuple[str, str]] = {
    "decompress": ("frustrations", "Need to decompress after demanding days."),
    "relief": ("emotional_signals", "Relief is a repeated emotional outcome."),
    "belonging": ("emotional_signals", "Belonging is a repeated emotional outcome."),
    "humor": ("repeated_language", "Specific humor helps make the experience recognizable."),
    "ritual": ("rituals", "A repeatable ritual is part of the audience experience."),
    "visible": ("repeated_language", "People want the experience made visible."),
}


def _signals_for_evidence(evidence: list[ResearchEvidence]) -> tuple[dict[str, list[str]], list[str]]:
    """Map observed words to transparent signal statements and supporting source IDs."""

    values: dict[str, list[str]] = defaultdict(list)
    evidence_ids: set[str] = set()
    for item in evidence:
        text = f"{item.title} {item.excerpt}".lower()
        matched = False
        for keyword, (group, statement) in SIGNAL_RULES.items():
            if keyword in text:
                if statement not in values[group]:
                    values[group].append(statement)
                matched = True
        if matched:
            evidence_ids.add(item.evidence_id)
    return values, sorted(evidence_ids)


def execute(input_data: ExperienceMiningInput) -> ExperienceMiningOutput:
    """Derive reproducible experience signals while preserving their evidence lineage."""

    evidence_by_niche: dict[str, list[ResearchEvidence]] = defaultdict(list)
    for item in input_data.evidence:
        evidence_by_niche[item.niche_id].append(item)

    signals: list[ExperienceSignal] = []
    for niche in input_data.niches:
        values, evidence_ids = _signals_for_evidence(evidence_by_niche[niche.niche_id])
        confidence = min(1.0, len(evidence_ids) / 3)
        all_signals = [value for group in values.values() for value in group]
        summary = (
            f"{niche.name} shows {', '.join(all_signals[:2]).lower()}"
            if all_signals
            else f"No recurring experience signal was observed for {niche.name}."
        )
        signals.append(
            ExperienceSignal(
                niche_id=niche.niche_id,
                repeated_language=values.get("repeated_language", []),
                frustrations=values.get("frustrations", []),
                rituals=values.get("rituals", []),
                emotional_signals=values.get("emotional_signals", []),
                evidence_ids=evidence_ids,
                confidence=round(confidence, 2),
                experience_summary=summary,
            )
        )
    return ExperienceMiningOutput(signals=signals)
