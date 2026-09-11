"""GitHub-style pipeline and stage summary components."""

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
        StageStatus.COMPLETED: "✅",
        StageStatus.RUNNING: "◉",
        StageStatus.FAILED: "⛔",
        StageStatus.SKIPPED: "—",
        StageStatus.PENDING: "○",
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


def _render_stage_preview(stage: StageFixture) -> None:
    """Render compact details inside an expanded stage without exposing private model reasoning."""

    st.caption(stage.output_summary)
    if stage.progress and stage.status == StageStatus.RUNNING:
        st.progress(stage.progress, text=f"Stage progress · {stage.progress}%")
    if stage.metrics:
        columns = st.columns(len(stage.metrics))
        for column, (label, value) in zip(columns, stage.metrics.items()):
            column.metric(label, value)


def render_pipeline(run: RunFixture) -> None:
    """Render all 17 stages as a grouped, expandable vertical pipeline."""

    st.markdown('<div class="opus-panel-title">Pipeline</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="opus-panel-subtitle">Expand a stage to inspect its summary, progress, and output.</div>',
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
        label = f"{icon}  {stage.number:02d} · {stage.name}   ·   {stage.duration}"
        with st.expander(label, expanded=stage.number == run.current_stage_number):
            st.markdown(
                f'<span style="color:{color}; font-size:0.78rem; font-weight:650;">'
                f'{stage.status.value.upper()}</span>',
                unsafe_allow_html=True,
            )
            _render_stage_preview(stage)

