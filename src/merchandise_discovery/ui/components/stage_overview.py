"""Human-facing renderers for stage outputs.

The pipeline receives structured stage snapshots, but clients should see decisions and artifacts
in domain language rather than storage-shaped JSON. Each renderer below owns one stage's visual
summary while shared helpers keep spacing, cards, scores, and empty states consistent.
"""

from collections.abc import Callable
from typing import Any

import streamlit as st

from merchandise_discovery.domain.models.common import StageStatus
from merchandise_discovery.ui.fixtures import StageFixture

PayloadRenderer = Callable[[dict[str, Any]], None]


def _records(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Return only object records from a payload collection so malformed provider data is safe."""

    value = payload.get(key, [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _text(record: dict[str, Any], *keys: str, default: str = "Not provided") -> str:
    """Read the first useful display value from a serialized stage record."""

    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return default


def _short(value: str, limit: int = 180) -> str:
    """Keep long model/provider text readable in a pipeline card."""

    return value if len(value) <= limit else f"{value[:limit - 1].rstrip()}…"


def _metric_row(values: list[tuple[str, str]]) -> None:
    """Render a compact metric row without requiring every stage to know column layout."""

    if not values:
        return
    columns = st.columns(len(values))
    for column, (label, value) in zip(columns, values):
        column.metric(label, value)


def _section(title: str) -> None:
    """Render the shared subsection label used inside each expanded stage."""

    st.markdown(f"**{title}**")


def _render_seed_discovery(payload: dict[str, Any]) -> None:
    seeds = _records(payload, "selected_seeds")
    reasons = payload.get("selection_reasons", {})
    evaluations = _records(payload, "evaluations")
    eval_by_id = {e.get("seed_id"): e for e in evaluations}
    _metric_row([
        ("Selected seed groups", str(len(seeds))),
        ("Selection seed", str(payload.get("selection_seed", "Not recorded"))),
        ("Executor", "LUNA + SYSTEM"),
        ("Cognitive Agent", "Luna (OpenAI reasoning)"),
    ])

    exec_summary = payload.get("executive_summary")
    if exec_summary:
        st.info(f"🌙 **Luna's Portfolio Strategy Summary:**\n\n{exec_summary}")

    _section("Selected seed groups")
    for seed in seeds:
        seed_id = seed.get("seed_id", "")
        with st.container(border=True):
            category = _text(seed, "category").upper()
            priority = _text(seed.get("metadata", {}), "priority", default="0")
            st.markdown(f"**{_text(seed, 'name')}** &nbsp; `[{category}]` &nbsp; `Priority: {priority}`")

            eval_item = eval_by_id.get(seed_id)
            if eval_item:
                if eval_item.get("selection_reason"):
                    st.markdown(f"🌙 **Luna's Strategic Rationale:** {eval_item['selection_reason']}")
                if eval_item.get("self_identification_strength"):
                    st.markdown(f"🏷️ **Self-Identification Strength:** {eval_item['self_identification_strength']}")
                if eval_item.get("community_language"):
                    st.markdown(f"💬 **Community Language & Tropes:** {eval_item['community_language']}")
                if eval_item.get("merchandise_potential"):
                    st.markdown(f"🛍️ **Merchandise Potential:** {eval_item['merchandise_potential']}")
                if eval_item.get("target_audience_appeal"):
                    st.markdown(f"🎯 **Target Audience Appeal:** {eval_item['target_audience_appeal']}")
            elif isinstance(reasons, dict) and seed_id in reasons:
                st.write(str(reasons[seed_id]))
            else:
                st.write("Selected by configured seed priority.")

            affinity_tags = seed.get("metadata", {}).get("affinity_tags", [])
            if isinstance(affinity_tags, list) and affinity_tags:
                st.caption(f"Affinity signals: {' · '.join(str(tag) for tag in affinity_tags)}")


def _render_identity_expansion(payload: dict[str, Any]) -> None:
    identities = _records(payload, "identities")
    _metric_row([("Expanded dimensions", str(len(identities)))])
    _section("Identity dimensions")
    for identity in identities[:12]:
        with st.container(border=True):
            st.markdown(f"**{_text(identity, 'value')}**")
            st.caption(
                f"{_text(identity, 'dimension_type')} · {_text(identity, 'category')} · "
                f"from {_text(identity, 'source_seed_name')}"
            )
            tags = identity.get("affinity_tags", [])
            if isinstance(tags, list) and tags:
                st.write(" · ".join(str(tag) for tag in tags))
    if len(identities) > 12:
        st.caption(f"Showing 12 of {len(identities)} expanded dimensions.")


def _render_intersections(payload: dict[str, Any]) -> None:
    intersections = _records(payload, "intersections")
    _metric_row([("Candidate intersections", str(len(intersections)))])
    _section("Candidate combinations")
    rows = [
        {
            "Identities": " + ".join(str(item) for item in record.get("identities", [])),
            "Shared signals": ", ".join(str(item) for item in record.get("metadata", {}).get("shared_tags", [])),
            "Candidate ID": _text(record, "intersection_id"),
        }
        for record in intersections
    ]
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)


def _render_coherence(payload: dict[str, Any]) -> None:
    intersections = _records(payload, "intersections")
    _metric_row([("Scored intersections", str(len(intersections)))])
    for record in intersections[:8]:
        score = float(record.get("coherence_score") or 0)
        with st.container(border=True):
            st.markdown(f"**{' + '.join(str(item) for item in record.get('identities', []))}**")
            st.progress(min(1.0, score / 10), text=f"Coherence {score:.1f} / 10")
            hypotheses = record.get("experience_hypotheses", [])
            if hypotheses:
                st.write(_short(str(hypotheses[0])))


def _render_filter(payload: dict[str, Any]) -> None:
    accepted = _records(payload, "accepted")
    rejected = _records(payload, "rejected")
    _metric_row([("Accepted", str(len(accepted))), ("Rejected", str(len(rejected)))])
    left, right = st.columns(2)
    with left:
        _section("Accepted for research")
        for record in accepted[:8]:
            st.success(" + ".join(str(item) for item in record.get("identities", [])))
    with right:
        _section("Filtered out")
        for record in rejected[:8]:
            st.warning(
                f"{' + '.join(str(item) for item in record.get('identities', []))}\n\n"
                f"{_text(record, 'filter_reason')}"
            )


def _render_research(payload: dict[str, Any]) -> None:
    niches = _records(payload, "niches")
    evidence = _records(payload, "evidence")
    _metric_row([("Niches researched", str(len(niches))), ("Evidence records", str(len(evidence)))])
    for niche in niches:
        with st.container(border=True):
            st.markdown(f"**{_text(niche, 'name')}**")
            st.caption(f"Evidence records: {_text(niche, 'evidence_count', default='0')}")
            niche_evidence = [item for item in evidence if item.get("niche_id") == niche.get("niche_id")]
            for item in niche_evidence[:2]:
                st.markdown(f"[{_text(item, 'title')}]({_text(item, 'url', default='#')})")
                st.write(_short(_text(item, "excerpt")))


def _render_experience_mining(payload: dict[str, Any]) -> None:
    signals = _records(payload, "signals")
    _metric_row([("Niches with signals", str(len(signals)))])
    for signal in signals:
        with st.container(border=True):
            st.markdown(f"**Niche {_text(signal, 'niche_id')}**")
            confidence = float(signal.get("confidence") or 0)
            st.progress(confidence, text=f"Evidence confidence {confidence:.0%}")
            for label, key in (
                ("Repeated language", "repeated_language"),
                ("Frustrations", "frustrations"),
                ("Rituals", "rituals"),
                ("Emotional signals", "emotional_signals"),
            ):
                values = signal.get(key, [])
                if isinstance(values, list) and values:
                    st.caption(label)
                    st.write(" · ".join(str(value) for value in values))
            st.info(_text(signal, "experience_summary"))


def _render_opportunity_scoring(payload: dict[str, Any]) -> None:
    scores = _records(payload, "scores")
    _metric_row([("Niches scored", str(len(scores)))])
    for score in scores:
        with st.container(border=True):
            st.markdown(f"**Niche {_text(score, 'niche_id')}**")
            overall = float(score.get("overall_score") or 0)
            st.progress(overall / 100, text=f"Opportunity score {overall:.1f} / 100")
            _metric_row(
                [
                    ("Evidence", f"{float(score.get('evidence_strength') or 0):.1f}"),
                    ("Clarity", f"{float(score.get('experience_clarity') or 0):.1f}"),
                    ("Audience fit", f"{float(score.get('audience_fit') or 0):.1f}"),
                    ("Differentiation", f"{float(score.get('differentiation') or 0):.1f}"),
                ]
            )
            st.caption(_text(score, "rationale"))


def _render_concepts(payload: dict[str, Any]) -> None:
    concepts = _records(payload, "concepts")
    _metric_row([("Concept candidates", str(len(concepts)))])
    for concept in concepts[:8]:
        with st.container(border=True):
            st.markdown(f"**{_text(concept, 'phrase')}**")
            st.write(_short(_text(concept, "description")))
            if concept.get("overall_score") is not None:
                st.progress(float(concept["overall_score"]) / 10, text=f"Score {float(concept['overall_score']):.1f} / 10")


def _render_critique(payload: dict[str, Any]) -> None:
    evaluations = _records(payload, "evaluations")
    kept = sum(_text(item, "verdict", default="reject") == "keep" for item in evaluations)
    _metric_row([("Reviewed", str(len(evaluations))), ("Kept", str(kept))])
    for evaluation in evaluations[:8]:
        with st.container(border=True):
            verdict = _text(evaluation, "verdict", default="pending").upper()
            st.markdown(f"**{_text(evaluation, 'concept_id')}** · {verdict}")
            _metric_row(
                [
                    ("Authenticity", f"{float(evaluation.get('authenticity') or 0):.1f}"),
                    ("Clarity", f"{float(evaluation.get('clarity') or 0):.1f}"),
                    ("Wearability", f"{float(evaluation.get('wearability') or 0):.1f}"),
                    ("Commercial", f"{float(evaluation.get('commercial_potential') or 0):.1f}"),
                ]
            )
            weaknesses = evaluation.get("weaknesses", [])
            if weaknesses:
                st.warning(" · ".join(str(item) for item in weaknesses))


def _render_similarity(payload: dict[str, Any]) -> None:
    checks = _records(payload, "checks")
    survivors = _records(payload, "survivors")
    rejected = _records(payload, "rejected")
    _metric_row([("Screened", str(len(checks))), ("Survivors", str(len(survivors))), ("Rejected", str(len(rejected)))])
    for check in checks:
        risk = _text(check, "risk_level", default="unknown").upper()
        if risk == "HIGH":
            st.error(f"{_text(check, 'concept_id')}: {_text(check, 'reason')}")
        else:
            st.success(f"{_text(check, 'concept_id')}: no duplicate found")


def _render_selection(payload: dict[str, Any]) -> None:
    finalists = _records(payload, "finalists")
    rejected = _records(payload, "rejected")
    _metric_row([("Finalists", str(len(finalists))), ("Not selected", str(len(rejected)))])
    _section("Selected finalists")
    for finalist in finalists:
        with st.container(border=True):
            st.markdown(f"**#{_text(finalist, 'rank')} · {_text(finalist, 'phrase')}**")
            st.caption(f"Score {float(finalist.get('overall_score') or 0):.1f} / 10")
            st.write(_short(_text(finalist, "description")))


def _render_briefs(payload: dict[str, Any]) -> None:
    briefs = _records(payload, "briefs")
    _metric_row([("Design briefs", str(len(briefs)))])
    for brief in briefs:
        with st.container(border=True):
            st.markdown(f"**Exact phrase: {_text(brief, 'exact_phrase')}**")
            st.caption(_text(brief, "target_audience"))
            _metric_row(
                [
                    ("Subject", _short(_text(brief, "main_subject"), 70)),
                    ("Style", _short(_text(brief, "illustration_style"), 70)),
                ]
            )
            st.write(_text(brief, "composition"))
            constraints = brief.get("constraints", [])
            if constraints:
                st.caption("Constraints: " + " · ".join(str(item) for item in constraints))


def _render_prompts(payload: dict[str, Any]) -> None:
    prompts = _records(payload, "prompts")
    _metric_row([("Prompts compiled", str(len(prompts)))])
    for prompt in prompts:
        with st.container(border=True):
            st.markdown(f"**Concept {_text(prompt, 'concept_id')}**")
            st.code(_text(prompt, "prompt"), language="text")


def _render_artwork_generation(payload: dict[str, Any]) -> None:
    artworks = _records(payload, "artworks")
    _metric_row([("Artwork candidates", str(len(artworks)))])
    for artwork in artworks:
        with st.container(border=True):
            st.markdown(f"**Candidate {_text(artwork, 'artwork_id')}**")
            _metric_row(
                [
                    ("Format", _text(artwork, "mime_type")),
                    ("Dimensions", f"{_text(artwork, 'width')} × {_text(artwork, 'height')}"),
                    ("Size", f"{_text(artwork, 'file_size_bytes')} bytes"),
                ]
            )
            url = _text(artwork, "source_url", default="")
            if url:
                st.markdown(f"Provider reference: [{url}]({url})")


def _render_artwork_critique(payload: dict[str, Any]) -> None:
    evaluations = _records(payload, "evaluations")
    accepted = sum(_text(item, "decision", default="") == "accept" for item in evaluations)
    _metric_row([("QA checked", str(len(evaluations))), ("Passed", str(accepted))])
    for evaluation in evaluations:
        with st.container(border=True):
            decision = _text(evaluation, "decision", default="pending").upper()
            st.markdown(f"**Artwork {_text(evaluation, 'artwork_id')}** · {decision}")
            _metric_row(
                [
                    ("Readability", f"{float(evaluation.get('readability') or 0):.1f}"),
                    ("Composition", f"{float(evaluation.get('composition') or 0):.1f}"),
                    ("Quality", f"{float(evaluation.get('quality') or 0):.1f}"),
                    ("Alignment", f"{float(evaluation.get('alignment') or 0):.1f}"),
                ]
            )
            checks = evaluation.get("checks", {})
            if isinstance(checks, dict):
                st.write(" · ".join(("✓ " if value else "✗ ") + str(key).replace("_", " ") for key, value in checks.items()))
            issues = evaluation.get("issues", [])
            if issues:
                st.warning(" · ".join(str(issue) for issue in issues))


def _render_approval(payload: dict[str, Any]) -> None:
    """Render the human-in-the-loop handoff as a clear action state."""

    status = _text(payload, "approval_status", default="Awaiting human approval")
    ready = _text(payload, "artworks_ready", default="0")
    _metric_row([("Artwork ready for review", ready)])
    st.info(status)
    st.caption("A reviewer decision will be persisted in the next workflow chunk.")


def _render_generic(payload: dict[str, Any]) -> None:
    """Provide a readable fallback for future stages without exposing raw JSON."""

    collections = [(key.replace("_", " ").title(), len(value)) for key, value in payload.items() if isinstance(value, list)]
    if collections:
        _metric_row([(label, str(count)) for label, count in collections[:4]])
    else:
        st.caption("This stage has persisted output, but no overview renderer is defined yet.")


RENDERERS: dict[int, PayloadRenderer] = {
    1: _render_seed_discovery,
    2: _render_identity_expansion,
    3: _render_intersections,
    4: _render_coherence,
    5: _render_filter,
    6: _render_research,
    7: _render_experience_mining,
    8: _render_opportunity_scoring,
    9: _render_concepts,
    10: _render_critique,
    11: _render_similarity,
    12: _render_selection,
    13: _render_briefs,
    14: _render_prompts,
    15: _render_artwork_generation,
    16: _render_artwork_critique,
    17: _render_approval,
}


def render_stage_overview(stage: StageFixture) -> None:
    """Render a stage's useful overview while preserving honest empty/pending states."""

    if stage.progress and stage.status == StageStatus.RUNNING:
        st.progress(stage.progress / 100, text=f"Stage progress · {stage.progress}%")
    if stage.metrics:
        _metric_row(list(stage.metrics.items()))
    if not stage.output_payload:
        if stage.status == StageStatus.PENDING:
            st.info(f"⏳ Stage {stage.number:02d} ({stage.name}) is pending execution. Pipeline execution halted at Stage 1 as configured by MVP_STOP_AFTER_STAGE.")
        else:
            st.info(stage.output_summary)
            st.caption("Structured stage output will appear here after execution.")
        return
    renderer = RENDERERS.get(stage.number, _render_generic)
    renderer(stage.output_payload)
