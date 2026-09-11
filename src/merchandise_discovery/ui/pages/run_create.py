"""Fixture-backed run creation page.

The form defines the inputs that will later be passed to DiscoveryService. Submission is intentionally
non-persistent in this UI chunk, making the interaction safe to demonstrate before worker execution
and repository wiring are connected.
"""

import streamlit as st


def render_run_create() -> None:
    """Render a demo configuration form for originating a new discovery run."""

    st.markdown('<div class="opus-breadcrumb">Workspace &nbsp;›&nbsp; New run</div>', unsafe_allow_html=True)
    st.title("Create a discovery run")
    st.caption("Define a small, observable funnel for the client demo.")

    with st.form("create-discovery-run"):
        title = st.text_input(
            "Run name",
            value="New merchandise discovery run",
            help="A human-readable name used in run history and review screens.",
        )
        seed_source = st.selectbox(
            "Seed source",
            ["MVP seed library", "Upload seed file (coming soon)", "Custom seed list (coming soon)"],
        )

        st.markdown("### Funnel limits")
        intersections = st.slider("Identity intersections", min_value=1, max_value=25, value=10)
        niches = st.slider("Niches to research", min_value=1, max_value=10, value=3)
        concepts = st.slider("Concepts per niche", min_value=1, max_value=10, value=5)
        artwork_variants = st.slider("Artwork variants per finalist", min_value=1, max_value=4, value=2)

        st.markdown("### Optional checks")
        similarity_check = st.checkbox("Enable similarity/IP screening", value=False)
        submitted = st.form_submit_button("Create demo run", use_container_width=True)

    if submitted:
        # Keep the draft visible after reruns so the client can see exactly what would be handed to
        # DiscoveryService; this record is not presented as a persisted run yet.
        st.session_state["last_run_draft"] = {
            "title": title,
            "seed_source": seed_source,
            "intersections": intersections,
            "niches": niches,
            "concepts": concepts,
            "artwork_variants": artwork_variants,
            "similarity_check": similarity_check,
        }
        st.success("Demo run configuration captured.")
        st.info("Worker execution and MongoDB persistence will be connected in the workflow chunk.")

