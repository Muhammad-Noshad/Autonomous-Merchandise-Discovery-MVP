"""Streamlit dashboard composition.

The dashboard owns presentation and user actions only. Durable workflow state belongs in the
application services and repositories, which keeps reruns and future UI replacements predictable.
"""

import streamlit as st

from merchandise_discovery.ui.pages.run_dashboard import render_run_dashboard


def main() -> None:
    """Render the MVP shell and expose the future workflow areas to the reviewer."""

    st.set_page_config(
        page_title="Autonomous Merchandise Discovery",
        page_icon="🛍️",
        layout="wide",
    )
    render_run_dashboard()
