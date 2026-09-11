"""Fixture-backed run listing page.

This page owns list presentation and navigation into a run. It deliberately does not query MongoDB;
the same component can later receive summaries from a run-list application service.
"""

import streamlit as st

from merchandise_discovery.domain.models.common import RunStatus
from merchandise_discovery.ui.components.layout import PAGE_RUN_DETAIL, navigate_to
from merchandise_discovery.ui.fixtures import RunListItemFixture, get_demo_runs


def _status_color(status: RunStatus) -> str:
    """Map a run status to the established Planet Opus semantic color."""

    return {
        RunStatus.COMPLETED: "#22C55E",
        RunStatus.RUNNING: "#8B5CF6",
        RunStatus.FAILED: "#EF4444",
        RunStatus.PENDING: "rgba(255,255,255,0.50)",
    }[status]


def _render_run_row(run: RunListItemFixture) -> None:
    """Render one run summary and route its action to the detail page."""

    with st.container(border=True):
        identity, status_column, progress_column, action_column = st.columns(
            [0.36, 0.18, 0.28, 0.18]
        )
        with identity:
            st.markdown(f"**#{run.run_id} · {run.title}**")
            st.caption(f"Triggered by {run.triggered_by} · Updated {run.updated}")
        with status_column:
            color = _status_color(run.status)
            st.markdown(
                f'<span style="color:{color}; font-weight:650;">●&nbsp; '
                f"{run.status.value.title()}</span>",
                unsafe_allow_html=True,
            )
        with progress_column:
            st.progress(run.progress / 100, text=f"{run.progress}% complete")
        with action_column:
            if st.button("Open", key=f"open-run-{run.run_id}", use_container_width=True):
                navigate_to(PAGE_RUN_DETAIL, run.run_id)


def render_run_list() -> None:
    """Render the run history landing page using stable demo summaries."""

    st.markdown('<div class="opus-breadcrumb">Workspace</div>', unsafe_allow_html=True)
    st.title("Runs")
    st.caption("Review discovery runs, inspect their pipeline progress, or start a new run.")

    toolbar_left, toolbar_right = st.columns([0.76, 0.24])
    with toolbar_left:
        st.markdown("### Run history")
    with toolbar_right:
        st.selectbox("Filter", ["All runs", "In progress", "Completed", "Failed"], label_visibility="collapsed")

    for run in get_demo_runs():
        _render_run_row(run)

    st.info("These are demo runs for the MVP shell. Live run history will be loaded from MongoDB in a later chunk.")

