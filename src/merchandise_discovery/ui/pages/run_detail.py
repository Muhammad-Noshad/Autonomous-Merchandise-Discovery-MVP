"""Run detail page for the expandable workflow pipeline."""

import streamlit as st

from merchandise_discovery.ui.components.details import render_detail_panel
from merchandise_discovery.ui.components.layout import PAGE_RUNS, navigate_to, render_run_header
from merchandise_discovery.ui.components.pipeline import render_pipeline
from merchandise_discovery.ui.fixtures import get_demo_run


def render_run_detail(run_id: str) -> None:
    """Render a detailed fixture when available, or an explicit historical-run placeholder."""

    if run_id != "017":
        st.markdown(f'<div class="opus-breadcrumb">Runs &nbsp;›&nbsp; #{run_id}</div>', unsafe_allow_html=True)
        st.title(f"Run #{run_id}")
        st.info("Historical run details will be loaded from MongoDB in a later chunk.")
        if st.button("Back to runs"):
            navigate_to(PAGE_RUNS)
        return

    run = get_demo_run()
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

