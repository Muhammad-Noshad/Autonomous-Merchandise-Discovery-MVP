"""Run detail page for the expandable workflow pipeline."""

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.adapters import snapshot_to_fixture
from merchandise_discovery.ui.components.details import render_detail_panel
from merchandise_discovery.ui.components.layout import PAGE_RUNS, navigate_to, render_run_header
from merchandise_discovery.ui.components.pipeline import render_pipeline
from merchandise_discovery.ui.fixtures import get_demo_run


def render_run_detail(
    run_id: str,
    discovery_service: DiscoveryService | None = None,
) -> None:
    """Render a persisted snapshot when available, or the demo detail in fixture mode."""

    if discovery_service is not None:
        try:
            snapshot = discovery_service.get_run_snapshot(run_id)
        except (PyMongoError, RepositoryError):
            st.error("Run details could not be loaded from MongoDB.")
            return
        if snapshot is None:
            st.error(f"Run {run_id} was not found.")
            if st.button("Back to runs"):
                navigate_to(PAGE_RUNS)
            return
        run = snapshot_to_fixture(snapshot)
    elif run_id == "017":
        run = get_demo_run()
    else:
        run = None

    if run is None:
        st.markdown(f'<div class="opus-breadcrumb">Runs &nbsp;›&nbsp; #{run_id}</div>', unsafe_allow_html=True)
        st.title(f"Run #{run_id}")
        st.info("Historical run details are not available in fixture mode.")
        if st.button("Back to runs"):
            navigate_to(PAGE_RUNS)
        return

    if st.session_state.get("created_run_id") == run_id:
        st.success("Run created and persisted. The worker is ready to claim it.")
        del st.session_state["created_run_id"]

    render_run_header(run)
    st.divider()

    pipeline_column, detail_column = st.columns([1.62, 1.0], gap="large")
    with pipeline_column:
        render_pipeline(run)
    with detail_column:
        selected_stage = next(
            stage for stage in run.stages if stage.number == run.current_stage_number
        )
        render_detail_panel(selected_stage)
