"""Stage 7: extract recurring audience experiences and language.

The stage owns the evidence-lineage contract, not the provider integration. OpenAI may interpret
the research evidence into structured signals, while this module verifies that every claim points
to evidence belonging to the same niche. The deterministic keyword implementation remains the
portable path for fixture mode or when no provider is configured; live provider errors are surfaced.
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


class MinedExperienceSignal(BaseModel):
    """Provider response for one niche before application-owned lineage validation."""

    niche_id: str = Field(min_length=1)
    repeated_language: list[str] = Field(default_factory=list, max_length=8)
    frustrations: list[str] = Field(default_factory=list, max_length=8)
    rituals: list[str] = Field(default_factory=list, max_length=8)
    emotional_signals: list[str] = Field(default_factory=list, max_length=8)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0, le=1)
    experience_summary: str = Field(min_length=1, max_length=500)


class Stage7ReasoningOutput(BaseModel):
    """Exact structured response expected from OpenAI for Stage 7."""

    signals: list[MinedExperienceSignal] = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=500)


class ExperienceMiningOutput(BaseModel):
    """All mined signals, retaining a one-to-many link back to stored evidence."""

    signals: list[ExperienceSignal]
    summary: str = ""
    model: str = "deterministic"


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


def _validate_provider_links(
    input_data: ExperienceMiningInput,
    reasoning_output: Stage7ReasoningOutput,
    stage_label: str = "Stage 7",
) -> dict[str, MinedExperienceSignal]:
    """Ensure one response exists per niche and every cited evidence ID is locally owned."""

    expected_ids = {niche.niche_id for niche in input_data.niches}
    returned_ids = [signal.niche_id for signal in reasoning_output.signals]
    if len(returned_ids) != len(set(returned_ids)):
        raise ValueError("Stage 7 provider output contains duplicate niche IDs.")
    returned_id_set = set(returned_ids)
    unknown_ids = returned_id_set - expected_ids
    missing_ids = expected_ids - returned_id_set
    if unknown_ids:
        raise ValueError(f"Stage 7 provider output contains unknown niche IDs: {sorted(unknown_ids)}.")
    if missing_ids:
        raise ValueError(f"Stage 7 provider output is missing niche IDs: {sorted(missing_ids)}.")

    evidence_by_niche: dict[str, set[str]] = defaultdict(set)
    for evidence in input_data.evidence:
        evidence_by_niche[evidence.niche_id].add(evidence.evidence_id)
    validated: dict[str, MinedExperienceSignal] = {}
    for signal in reasoning_output.signals:
        allowed_evidence = evidence_by_niche[signal.niche_id]
        unknown_evidence = set(signal.evidence_ids) - allowed_evidence
        if unknown_evidence:
            raise ValueError(
                f"{stage_label} provider output cites evidence outside niche {signal.niche_id}: "
                f"{sorted(unknown_evidence)}."
            )
        signal_groups = (
            signal.repeated_language,
            signal.frustrations,
            signal.rituals,
            signal.emotional_signals,
        )
        if any(signal_groups) and not signal.evidence_ids:
            raise ValueError(
                f"{stage_label} provider output makes unsupported claims for niche {signal.niche_id}."
            )
        validated[signal.niche_id] = signal
    return validated


def execute(
    input_data: ExperienceMiningInput,
    reasoning_output: Stage7ReasoningOutput | None = None,
    model: str = "deterministic",
    validation_label: str = "Stage 7",
) -> ExperienceMiningOutput:
    """Derive signals from evidence or normalize a validated provider interpretation."""

    evidence_by_niche: dict[str, list[ResearchEvidence]] = defaultdict(list)
    for item in input_data.evidence:
        evidence_by_niche[item.niche_id].append(item)

    provider_by_niche = (
        _validate_provider_links(input_data, reasoning_output, validation_label)
        if reasoning_output is not None
        else {}
    )
    signals: list[ExperienceSignal] = []
    for niche in input_data.niches:
        provider_signal = provider_by_niche.get(niche.niche_id)
        if provider_signal is not None:
            signals.append(
                ExperienceSignal(
                    niche_id=niche.niche_id,
                    repeated_language=provider_signal.repeated_language,
                    frustrations=provider_signal.frustrations,
                    rituals=provider_signal.rituals,
                    emotional_signals=provider_signal.emotional_signals,
                    evidence_ids=list(dict.fromkeys(provider_signal.evidence_ids)),
                    confidence=provider_signal.confidence,
                    experience_summary=provider_signal.experience_summary.strip(),
                )
            )
            continue
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
    return ExperienceMiningOutput(
        signals=signals,
        summary=reasoning_output.summary if reasoning_output is not None else "",
        model=model,
    )
