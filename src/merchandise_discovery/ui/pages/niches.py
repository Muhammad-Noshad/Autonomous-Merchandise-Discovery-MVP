"""Niche page showing dummy data from a JSON file."""

import json
import os
import uuid
import streamlit as st

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.ui.pages.placeholder import render_placeholder_page

JSON_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "data", "dummy_niches.json"
)


def load_niches() -> list[dict]:
    """Load niches from the dummy JSON file."""
    if not os.path.exists(JSON_PATH):
        return []
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_niches(niches: list[dict]) -> None:
    """Save niches to the dummy JSON file."""
    os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(niches, f, indent=2)


def _render_niche(niche: dict) -> None:
    """Render a single Niche candidate."""
    with st.container(border=True):
        st.markdown(f"**{niche.get('name', 'Unnamed Niche')}**")

        validated = niche.get("validated", False)
        status = "Validated" if validated else "Unvalidated"
        color = "#22C55E" if validated else "#EAB308"

        st.markdown(
            f'<span style="color:{color}; font-weight:650;">●&nbsp; {status}</span>',
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            if niche.get("coherence_score") is not None:
                st.caption(f"Coherence score: {niche['coherence_score']:.2f} / 10")
        with col2:
            if niche.get("opportunity_score") is not None:
                st.caption(f"Opportunity score: {niche['opportunity_score']:.2f} / 100")

        if niche.get("experience_summary"):
            st.write(niche["experience_summary"])

        st.caption(f"Evidence count: {niche.get('evidence_count', 0)}")


def render_niches(discovery_service: DiscoveryService | None = None) -> None:
    """Render dummy niches and allow adding new ones."""
    st.markdown('<div class="opus-breadcrumb">Workspace</div>', unsafe_allow_html=True)
    st.title("Niches")
    st.caption("Inspect and add manual identity intersections for merchandise discovery.")

    niches = load_niches()

    st.subheader("Add a New Niche")
    with st.form("add_niche_form", clear_on_submit=True):
        name = st.text_input("Niche Name (e.g., Night Shift ICU Nurse)")
        experience = st.text_area("Experience Summary")
        coherence = st.slider("Coherence Score", 0.0, 10.0, 5.0, 0.1)
        opportunity = st.slider("Opportunity Score", 0.0, 100.0, 50.0, 1.0)

        submitted = st.form_submit_button("Add Niche")
        if submitted:
            if not name.strip():
                st.error("Niche name is required.")
            else:
                new_niche = {
                    "niche_id": str(uuid.uuid4()),
                    "run_id": "dummy-run",
                    "intersection_id": f"manual-{uuid.uuid4()}",
                    "name": name.strip(),
                    "coherence_score": coherence,
                    "experience_summary": experience.strip(),
                    "opportunity_score": opportunity,
                    "evidence_count": 0,
                    "validated": False,
                }
                niches.append(new_niche)
                save_niches(niches)
                st.success(f"Added niche: {name}")
                st.rerun()

    st.subheader("Available Niches")
    if not niches:
        st.info("No niches found in the dummy JSON file.")
        return

    st.metric("Total Niches", len(niches))
    for niche in niches:
        _render_niche(niche)
