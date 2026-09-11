"""Merchandise concept page entrypoint."""

from merchandise_discovery.ui.pages.placeholder import render_placeholder_page


def render_concepts() -> None:
    """Render the future concept generation and finalist-selection workspace."""

    render_placeholder_page(
        "Concepts",
        "Inspect experience-led merchandise concepts, critiques, and finalist rankings.",
        [
            ("Generated concepts", "Concept cards and source niches will appear here."),
            ("Critique signals", "Authenticity, wearability, and commercial scores will appear here."),
            ("Finalists", "Selected concepts will move into design-brief generation."),
        ],
    )

