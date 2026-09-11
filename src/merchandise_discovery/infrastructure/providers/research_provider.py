"""Research provider boundary and deterministic local implementation.

The domain asks for source-backed observations through this interface and never knows whether the
records came from a fixture, a search API, or a future browser worker. The MVP default is local and
network-free so demos remain repeatable and do not silently spend API credits.
"""

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ResearchRequest:
    """Context supplied to a research provider for one candidate niche."""

    query: str
    identities: tuple[str, ...]
    hypotheses: tuple[str, ...]


@dataclass(frozen=True)
class ResearchDocument:
    """Provider-neutral source record before it receives a niche and run identity."""

    url: str
    title: str
    source: str
    excerpt: str
    evidence_type: str = "public_web"


class ResearchProvider(Protocol):
    """Contract implemented by fixture and external research providers."""

    def search(self, request: ResearchRequest) -> list[ResearchDocument]:
        """Return source records for a bounded niche query."""


class FixtureResearchProvider:
    """Return realistic, repeatable source records without making network requests."""

    def search(self, request: ResearchRequest) -> list[ResearchDocument]:
        """Generate three provenance-bearing observations for one candidate niche.

        These records deliberately look like provider output while remaining clearly attributable
        to the MVP fixture. Replacing this class with a live adapter does not change Stage 6.
        """

        slug = re.sub(r"[^a-z0-9]+", "-", request.query.lower()).strip("-")
        audience = " and ".join(request.identities)
        hypothesis = request.hypotheses[0] if request.hypotheses else "a shared experience"
        return [
            ResearchDocument(
                url=f"https://fixture.local/community/{slug}",
                title=f"Community discussion: {audience}",
                source="MVP research fixture",
                excerpt=(
                    f"People describing {audience} repeatedly discuss how to decompress after "
                    f"demanding days. The recurring experience is {hypothesis.lower()} ."
                ),
            ),
            ResearchDocument(
                url=f"https://fixture.local/marketplace/{slug}",
                title=f"Marketplace language review: {audience}",
                source="MVP research fixture",
                excerpt=(
                    f"Existing merchandise often uses broad identity language for {audience}; "
                    "specific humor and recognizable rituals appear less served."
                ),
            ),
            ResearchDocument(
                url=f"https://fixture.local/search/{slug}",
                title=f"Search interest snapshot: {audience}",
                source="MVP research fixture",
                excerpt=(
                    f"Independent public conversations connect {audience} with belonging, "
                    "relief, and practical ways to make the experience visible."
                ),
            ),
        ]
