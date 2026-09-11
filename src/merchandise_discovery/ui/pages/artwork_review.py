"""Artwork review page entrypoint."""

from merchandise_discovery.ui.pages.placeholder import render_placeholder_page


def render_artwork_review() -> None:
    """Render the future artwork QA and human-approval workspace."""

    render_placeholder_page(
        "Artwork Review",
        "Review generated artwork candidates and record the final human decision.",
        [
            ("Candidates", "Artwork variants and generation metadata will appear here."),
            ("QA results", "Readability, composition, and format checks will appear here."),
            ("Approval queue", "Approve, reject, regenerate, and request adjustments here."),
        ],
    )

