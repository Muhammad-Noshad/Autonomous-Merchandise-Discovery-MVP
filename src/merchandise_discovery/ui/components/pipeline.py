"""GitHub-style pipeline layout and stage shell.

The pipeline owns grouping, status, and expansion behavior. Domain-specific output presentation is
delegated to ``stage_overview`` so each stage can evolve without turning this layout into a large
conditional renderer.
"""

import streamlit as st

from merchandise_discovery.domain.models.common import StageStatus
from merchandise_discovery.ui.components.stage_overview import render_stage_overview
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


def _render_stage_preview(stage: StageFixture) -> None:
    """Render common context before the stage-specific overview."""

    st.markdown("**Purpose**")
    st.write(stage.summary)
    st.markdown("**Result**")
    st.caption(stage.output_summary)
    render_stage_overview(stage)


def render_pipeline(run: RunFixture) -> None:
    """Render all 17 stages as a grouped, expandable vertical pipeline."""

    st.markdown('<div class="opus-panel-title">Pipeline</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="opus-panel-subtitle">Expand a stage to inspect its purpose, decisions, and output.</div>',
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
        is_expanded = (
            stage.number == run.current_stage_number
            or (stage.number == 1 and stage.status == StageStatus.COMPLETED)
        )
        with st.expander(label, expanded=is_expanded):
            st.markdown(
                f'<span style="color:{color}; font-size:0.78rem; font-weight:650;">'
                f'{stage.status.value.upper()}</span>',
                unsafe_allow_html=True,
            )
            if stage.error_message:
                st.error(stage.error_message)
            _render_stage_preview(stage)
