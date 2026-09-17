"""Research provider boundary, fixture adapter, and OpenAI web-search implementation.

The domain asks for source-backed observations through this interface and never knows whether the
records came from a fixture, a search API, or a future browser worker. The MVP default is local and
network-free so demos remain repeatable and do not silently spend API credits.
"""

import re
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI, OpenAIError

from merchandise_discovery.domain.models.usage import UsageMetrics


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


@dataclass(frozen=True)
class ResearchSearchResult:
    """Source claims, the complete provider synthesis, and usage for one research request."""

    documents: list[ResearchDocument]
    usage: UsageMetrics
    summary: str = ""


class ResearchProvider(Protocol):
    """Contract implemented by fixture and external research providers."""

    def search(self, request: ResearchRequest) -> ResearchSearchResult:
        """Return source records and usage for a bounded niche query."""


class FixtureResearchProvider:
    """Return realistic, repeatable source records without making network requests."""

    def search(self, request: ResearchRequest) -> ResearchSearchResult:
        """Generate three provenance-bearing observations for one candidate niche.

        These records deliberately look like provider output while remaining clearly attributable
        to the MVP fixture. Replacing this class with a live adapter does not change Stage 6.
        """

        slug = re.sub(r"[^a-z0-9]+", "-", request.query.lower()).strip("-")
        audience = " and ".join(request.identities)
        hypothesis = request.hypotheses[0] if request.hypotheses else "a shared experience"
        documents = [
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
        return ResearchSearchResult(documents=documents, usage=UsageMetrics())


def _citation_excerpt(summary: str, annotation: object) -> str:
    """Extract the claim-sized sentence surrounding one citation marker.

    Responses annotations identify where a URL citation occurs in the assistant text, not the
    body of the cited webpage. Selecting the nearby sentence gives downstream stages a bounded
    source claim while avoiding the previous mistake of assigning the entire response to every URL.
    """

    start = getattr(annotation, "start_index", None)
    end = getattr(annotation, "end_index", None)
    if not isinstance(start, int) or not isinstance(end, int) or not summary:
        return "Source-local excerpt unavailable; see the stored research summary."

    start = max(0, min(start, len(summary)))
    end = max(start, min(end, len(summary)))
    left_candidates = [
        summary.rfind("\n", 0, start),
        summary.rfind(".", 0, start),
        summary.rfind("?", 0, start),
        summary.rfind("!", 0, start),
    ]
    left = max(left_candidates) + 1
    # The API's end position is represented as the last character in some response shapes and
    # immediately after the span in others. Starting one character earlier handles both without
    # consuming the next claim when the citation follows a sentence-ending period.
    right_boundary = max(start, end - 1)
    right_candidates = [
        position
        for position in (
            summary.find("\n", right_boundary),
            summary.find(".", right_boundary),
            summary.find("?", right_boundary),
            summary.find("!", right_boundary),
        )
        if position >= 0
    ]
    right = min(right_candidates, default=len(summary))
    excerpt = summary[left:right + 1].strip()
    return excerpt[:2_000] or "Source-local excerpt unavailable; see the stored research summary."


class OpenAIWebResearchProvider:
    """Use OpenAI Responses web search to collect source-linked public evidence."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        *,
        input_price_per_million: float = 0.15,
        output_price_per_million: float = 0.60,
        web_search_price_per_call: float = 0.01,
    ):
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._input_price = input_price_per_million
        self._output_price = output_price_per_million
        self._web_search_price_per_call = web_search_price_per_call

    def search(self, request: ResearchRequest) -> ResearchSearchResult:
        """Search the public web and retain citation URLs as evidence provenance."""

        prompt = (
            f"Research this merchandise audience intersection: {request.query}. "
            f"Relevant identities: {', '.join(request.identities)}. "
            f"Initial hypotheses: {'; '.join(request.hypotheses) or 'none'}. "
            "Find independent public sources that support recurring experiences, frustrations, "
            "rituals, or language. Return a concise research summary, then list each source in its "
            "own bullet with one source-specific claim and place that source's citation immediately "
            "after the claim. Do not combine multiple sources in one bullet and do not reuse the "
            "same claim for every source."
        )
        try:
            response = self._client.responses.create(
                model=self._model,
                tools=[{"type": "web_search"}],
                input=prompt,
            )
        except (OpenAIError, TypeError, ValueError) as error:
            raise RuntimeError("OpenAI web research request failed.") from error

        documents: list[ResearchDocument] = []
        seen_urls: set[str] = set()
        summary = (response.output_text or "").strip()
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                for annotation in getattr(content, "annotations", []) or []:
                    url = getattr(annotation, "url", None)
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    documents.append(
                        ResearchDocument(
                            url=url,
                            title=getattr(annotation, "title", None) or url,
                            source="OpenAI web search",
                            excerpt=_citation_excerpt(summary, annotation),
                        )
                    )
        if not documents:
            raise RuntimeError("OpenAI web research returned no cited sources.")

        provider_usage = response.usage
        input_tokens = int(getattr(provider_usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(provider_usage, "output_tokens", 0) or 0)
        return ResearchSearchResult(
            documents=documents,
            usage=UsageMetrics(
                provider="openai",
                model=self._model,
                request_count=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=int(
                    getattr(provider_usage, "total_tokens", input_tokens + output_tokens)
                    or input_tokens + output_tokens
                ),
                estimated_cost_usd=round(
                    input_tokens * self._input_price / 1_000_000
                    + output_tokens * self._output_price / 1_000_000
                    + self._web_search_price_per_call,
                    8,
                ),
                cost_is_estimate=True,
                pricing_note=(
                    "Estimated token cost plus $"
                    f"{self._web_search_price_per_call:.2f} per OpenAI web-search call."
                ),
            ),
            summary=summary,
        )
