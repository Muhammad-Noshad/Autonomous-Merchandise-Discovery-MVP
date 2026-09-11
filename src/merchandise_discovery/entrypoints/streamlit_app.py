"""Streamlit dashboard composition.

The dashboard owns presentation and user actions only. Durable workflow state belongs in the
application services and repositories, which keeps reruns and future UI replacements predictable.
"""

import streamlit as st


def main() -> None:
    """Render the MVP shell and expose the future workflow areas to the reviewer."""

    st.set_page_config(
        page_title="Autonomous Merchandise Discovery",
        page_icon="🛍️",
        layout="wide",
    )
    st.title("Autonomous Merchandise Discovery")
    st.caption("MVP foundation — discovery, validation, concepts, artwork, and approval")

    st.info(
        "Project foundation is ready. The first executable discovery workflow will be added in the "
        "next implementation chunk."
    )

    with st.sidebar:
        st.subheader("Workflow areas")
        st.write("Discovery runs")
        st.write("Niches and evidence")
        st.write("Concept critique")
        st.write("Artwork review")

