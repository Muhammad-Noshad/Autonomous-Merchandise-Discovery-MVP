"""Composition root for the fixture-backed discovery run dashboard."""

import streamlit as st

from merchandise_discovery.ui.components.details import render_detail_panel
from merchandise_discovery.ui.components.layout import render_run_header, render_sidebar
from merchandise_discovery.ui.components.pipeline import render_pipeline
from merchandise_discovery.ui.fixtures import get_demo_run
from merchandise_discovery.ui.theme import apply_theme


def render_run_dashboard() -> None:
    """Render the client-facing UI shell using a stable fixture until persistence is connected."""

    apply_theme()
    run = get_demo_run()
    render_sidebar(run)
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

