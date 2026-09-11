"""GitHub-style pipeline and stage summary components.

The pipeline owns presentation only. Stage purpose and execution snapshots arrive through the
stable UI fixture model, which keeps this component independent from MongoDB and stage internals.
"""

import streamlit as st

from merchandise_discovery.domain.models.common import StageStatus
from merchandise_discovery.ui.fixtures import RunFixture, StageFixture

PHASES = {
    1: "Discover",
    6: "Validate",
    9: "Concepts",
    12: "Select",
    13: "Artwork",
    17: "Approve",
}


def _status_icon(status: StageStatus) -> str:
    """Map persisted stage status to a compact, familiar pipeline marker."""

    return {
        StageStatus.COMPLETED: "\u2705",
        StageStatus.RUNNING: "\u25c9",
        StageStatus.FAILED: "\u26d4",
        StageStatus.SKIPPED: "\u2014",
        StageStatus.PENDING: "\u25cb",
    }[status]


def _status_color(status: StageStatus) -> str:
    """Return the Planet Opus semantic color for a stage status."""

    return {
        StageStatus.COMPLETED: "#22C55E",
        StageStatus.RUNNING: "#8B5CF6",
        StageStatus.FAILED: "#EF4444",
        StageStatus.SKIPPED: "rgba(255,255,255,0.45)",
        StageStatus.PENDING: "rgba(255,255,255,0.50)",
    }[status]


def _render_output_signal(payload: dict[str, object]) -> None:
    """Summarize common collection outputs before the raw snapshot is shown."""

    collection_labels = {
        "selected_seeds": "Selected seeds",
        "identities": "Expanded identities",
        "intersections": "Intersections",
        "all_intersections": "Candidate intersections",
        "accepted": "Accepted candidates",
        "rejected": "Rejected candidates",
        "evidence": "Evidence records",
        "concepts": "Concepts",
        "artifacts": "Artifacts",
    }
    signals = [
        f"{label}: {len(payload[key])}"
        for key, label in collection_labels.items()
        if isinstance(payload.get(key), list)
    ]
    if signals:
        st.caption(" \u00b7 ".join(signals))


def _render_stage_preview(stage: StageFixture) -> None:
    """Render purpose, progress, decision signals, and persisted stage snapshots."""

    st.markdown("**Purpose**")
    st.write(stage.summary)
    st.markdown("**Result**")
    st.info(stage.output_summary)
    if stage.progress and stage.status == StageStatus.RUNNING:
        st.progress(stage.progress, text=f"Stage progress \u00b7 {stage.progress}%")
    if stage.metrics:
        columns = st.columns(len(stage.metrics))
        for column, (label, value) in zip(columns, stage.metrics.items()):
            column.metric(label, value)

    if stage.input_payload:
        st.markdown("**Input snapshot**")
        st.json(stage.input_payload, expanded=False)
    else:
        st.caption("No input snapshot was persisted for this stage.")

    if stage.output_payload:
        st.markdown("**Output snapshot**")
        _render_output_signal(stage.output_payload)
        st.json(stage.output_payload, expanded=False)
    else:
        st.caption("No output snapshot is available until this stage executes.")


def render_pipeline(run: RunFixture) -> None:
    """Render all 17 stages as a grouped, expandable vertical pipeline."""

    st.markdown('<div class="opus-panel-title">Pipeline</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="opus-panel-subtitle">Expand a stage to inspect its purpose, inputs, decisions, and output.</div>',
        unsafe_allow_html=True,
    )

    for stage in run.stages:
        if stage.number in PHASES:
            st.markdown(
                f'<div style="color:#C4B5FD; font-size:0.75rem; font-weight:700; '
                f'text-transform:uppercase; letter-spacing:0.12em; margin:1rem 0 0.45rem;">'
                f'{PHASES[stage.number]}</div>',
                unsafe_allow_html=True,
            )

        icon = _status_icon(stage.status)
        color = _status_color(stage.status)
        label = f"{icon}  {stage.number:02d} \u00b7 {stage.name}   \u00b7   {stage.duration}"
        with st.expander(label, expanded=stage.number == run.current_stage_number):
            st.markdown(
                f'<span style="color:{color}; font-size:0.78rem; font-weight:650;">'
                f'{stage.status.value.upper()}</span>',
                unsafe_allow_html=True,
            )
            if stage.error_message:
                st.error(stage.error_message)
            _render_stage_preview(stage)
