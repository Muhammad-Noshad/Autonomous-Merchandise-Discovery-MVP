"""Social behavior to merchandise-text pipeline contract.

This pipeline intentionally collapses discovery into one provider call: OpenAI searches the
selected public social domains, extracts concrete lived behavior, and proposes text-first
merchandise copy. The domain module owns the structured contract and validation; the application
layer owns provider injection and persistence.
"""

from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from merchandise_discovery.domain.models.common import SocialSource


class SocialBehaviorTextInput(BaseModel):
    """User-defined social search scope and output bound for one run."""

    sources: list[SocialSource] = Field(min_length=1)
    query: str = Field(min_length=3, max_length=500)
    candidate_count: int = Field(ge=1, le=25)


class SocialBehaviorTextCandidate(BaseModel):
    """One source-backed behavior and the merchandise text derived from it."""

    source_platform: SocialSource
    source_url: str = Field(min_length=1)
    source_title: str = Field(min_length=1, max_length=300)
    source_excerpt: str = Field(min_length=1, max_length=2_000)
    audience_context: str = Field(min_length=1, max_length=500)
    behavior: str = Field(min_length=1, max_length=500)
    friction_or_pressure: str = Field(min_length=1, max_length=500)
    # Targeted-shirt copy may need a full sentence or two to explain the private joke. The prompt
    # controls usefulness and readability; an arbitrary slogan-length ceiling would remove context.
    artwork_text: str = Field(min_length=8)
    specificity_reason: str = Field(min_length=1, max_length=700)

    @field_validator("source_url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        """Reject fabricated non-web references while allowing provider-specific URL shapes."""

        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url must be an absolute HTTP(S) URL")
        return value


class SocialBehaviorTextOutput(BaseModel):
    """Complete structured response returned by the single social discovery call."""

    candidates: list[SocialBehaviorTextCandidate] = Field(min_length=1, max_length=25)
    search_summary: str = Field(min_length=1, max_length=2_000)
    model: str = "deterministic"


def reasoning_instructions() -> str:
    """Return the provider contract for standalone, concrete, audience-recognizable copy."""

    return (
        "You are a merchandise discovery researcher and text-first copywriter. Use the supplied "
        "web search tool to inspect public discussions from the requested Reddit and/or X domains. "
        "Extract concrete repeated behavior, not broad labels or demographic stereotypes. Look for "
        "the small lived action, routine, contradiction, friction, or ordinary pressure that an "
        "insider would recognize. Then write one original merchandise line for each behavior. "
        "The merchandise line is the primary product output and MUST make sense when read alone, "
        "without the observed behavior, friction, or specificity fields. It should make the target "
        "person think 'that is literally me'. Write in the style of a targeted T-shirt: personal, "
        "blunt, matter-of-fact, context-rich, slightly provocative, and understandable to an "
        "outsider. The line should sound like a specific person or relationship making a claim, "
        "confession, complaint, or dry observation—not like an advertising slogan, product title, "
        "mission statement, or category label. Treat each line as a self-contained mini-story with "
        "three ingredients: who or what situation this is about, the concrete duty or behavior, and "
        "the consequence, contradiction, or emotional payoff. Use a time, role, setting, duration, "
        "specific object, or exact action when the source supports it. A reader should understand the "
        "premise without seeing the metadata. Do not compress the idea into a vague aphorism such as "
        "'my shift ended but my brain did not' unless the line also explains what kind of shift or "
        "specific experience makes it recognizable. Preserve the personal relationship, concrete "
        "scene, ordinary detail, exact object or action, and emotional contradiction that make the "
        "behavior recognizable. If a pronoun such as 'she', 'he', or 'they' would be unclear without "
        "metadata, name the person or relationship in the line. Use as many words as needed to tell "
        "the premise clearly; there is no hard length limit. A second clause, setup, or sentence is "
        "encouraged when it makes the private joke legible. Prefer irony or a recognizable absurd "
        "collision where supported by the source. After drafting, edit each line like a T-shirt copy "
        "editor: keep one dominant scene or behavior, one or two details that make it personal, and "
        "one clear contradiction or payoff. Remove source-detail lists, excessive statistics, extra "
        "timelines, multiple examples, and explanations that do not improve recognition or humor. "
        "The line should feel specific without reading like a case summary or study plan. Avoid "
        "generic achievement statements, broad labels, abstract praise, and lines that only say "
        "someone is proud, calm, busy, or untraditional. Keep the niche detail in the actual "
        "merchandise line, not only in the metadata. This is text-first merchandise: do not describe "
        "an illustration, do not generate a visual prompt, and do not force every line into an 'I ...' "
        "template. Preserve source URLs and provide a source-specific excerpt. Return only the "
        "requested structured output."
    )


def build_user_prompt(input_model: SocialBehaviorTextInput) -> str:
    """Build the single-call request from user scope and source-domain instructions."""

    platforms = ", ".join(source.value for source in input_model.sources)
    return (
        f"Search these public platforms: {platforms}.\n"
        f"Behavior/topic to investigate: {input_model.query}\n"
        f"Return up to {input_model.candidate_count} distinct behavior-based merchandise text "
        "candidates. Avoid repeating the same audience pressure or behavior in different wording. "
        "Before returning each line, check that a reader can understand who, what, and why it is "
        "funny or emotionally recognizable without reading any other field. Write like targeted "
        "T-shirt copy: use the real relationship, scene, behavior, or object instead of compressing "
        "it into a generic slogan. Verify that the line contains the situation, action, and consequence "
        "in a readable way; use as many words as needed to make the premise clear. Each "
        "candidate must cite one directly relevant source URL "
        "from the searched platforms."
    )


def execute(
    input_model: SocialBehaviorTextInput,
    *,
    reasoning_output: SocialBehaviorTextOutput | None = None,
    model: str = "deterministic",
) -> SocialBehaviorTextOutput:
    """Validate live output or produce an explicit fixture result for local demos."""

    if reasoning_output is not None:
        if len(reasoning_output.candidates) > input_model.candidate_count:
            raise ValueError(
                "Social behavior provider returned more candidates than the configured limit."
            )
        allowed_sources = set(input_model.sources)
        invalid_sources = [
            candidate.source_platform.value
            for candidate in reasoning_output.candidates
            if candidate.source_platform not in allowed_sources
        ]
        if invalid_sources:
            raise ValueError(
                "Social behavior provider returned candidates from unrequested sources: "
                + ", ".join(sorted(set(invalid_sources)))
            )
        for candidate in reasoning_output.candidates:
            hostname = (urlparse(candidate.source_url).hostname or "").lower()
            if candidate.source_platform == SocialSource.REDDIT:
                valid_domain = hostname == "reddit.com" or hostname.endswith(".reddit.com")
            else:
                valid_domain = hostname in {"x.com", "twitter.com"} or hostname.endswith(
                    (".x.com", ".twitter.com")
                )
            if not valid_domain:
                raise ValueError(
                    f"Social behavior provider cited {candidate.source_url!r} for "
                    f"{candidate.source_platform.value}; expected the selected platform domain."
                )
        return reasoning_output.model_copy(update={"model": model})

    source = input_model.sources[0]
    candidates = [
        SocialBehaviorTextCandidate(
            source_platform=source,
            source_url=f"https://fixture.local/{source.value}/behavior/{index}",
            source_title=f"Fixture {source.value} behavior {index}",
            source_excerpt=(
                f"Fixture discussion about the behavior described by: {input_model.query}."
            ),
            audience_context=input_model.query,
            behavior=f"People repeatedly describe the routine of {input_model.query}.",
            friction_or_pressure="The routine collides with the ordinary pressure of keeping daily life moving.",
            artwork_text=f"Still doing {input_model.query}",
            specificity_reason="Fixture output only; replace with live source-backed behavior in live mode.",
        )
        for index in range(1, input_model.candidate_count + 1)
    ]
    return SocialBehaviorTextOutput(
        candidates=candidates,
        search_summary="Deterministic fixture output; no social platform was queried.",
        model=model,
    )
