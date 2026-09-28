"""Identity-focused social discussions to merchandise-text pipeline contract.

This is deliberately a separate contract from ``social_behavior_text``. Both pipelines search the
same public sources and generate the same two output kinds, but this variant makes an explicit
identity a first-class input and validates that every candidate preserves it. That separation keeps
the original social pipeline as an honest A/B control instead of silently changing its behavior.
"""

from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from merchandise_discovery.domain.models.common import IdentityType, SocialSource


class SocialIdentityTextInput(BaseModel):
    """User-defined source scope, identity anchor, and output bound for one run."""

    sources: list[SocialSource] = Field(min_length=1)
    identity: str = Field(default="", max_length=300)
    identity_type: IdentityType | None = None
    auto_identity: bool = False
    query: str = Field(default="", max_length=500)
    auto_topic: bool = False
    candidate_count: int = Field(ge=1, le=25)

    @field_validator("identity")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        """Reject whitespace-only identity anchors before they reach a provider prompt."""

        return value.strip()

    @model_validator(mode="after")
    def validate_topic_source(self) -> "SocialIdentityTextInput":
        """Require a manual topic only when the user has not delegated discovery to AI."""

        if not self.auto_identity and len(self.identity) < 2:
            raise ValueError("identity must contain at least 2 characters unless auto_identity is enabled")
        if not self.auto_identity and self.identity_type is None:
            raise ValueError("identity_type is required unless auto_identity is enabled")
        if not self.auto_topic and len(self.query.strip()) < 3:
            raise ValueError("query must contain at least 3 characters unless auto_topic is enabled")
        return self


class SocialIdentityTextCandidate(BaseModel):
    """One source-backed identity behavior and the merchandise direction derived from it."""

    identity: str = Field(min_length=2, max_length=300)
    identity_type: IdentityType
    identity_evidence: str = Field(min_length=1, max_length=700)
    source_platform: SocialSource
    source_url: str = Field(min_length=1)
    source_title: str = Field(min_length=1, max_length=300)
    source_excerpt: str = Field(min_length=1, max_length=2_000)
    audience_context: str = Field(min_length=1, max_length=500)
    behavior: str = Field(min_length=1, max_length=500)
    friction_or_pressure: str = Field(min_length=1, max_length=500)
    artwork_text: str = Field(min_length=8)
    artwork_prompt: str = Field(min_length=20, max_length=4_000)
    visual_punchline: str = Field(min_length=1, max_length=500)
    main_visual_metaphor: str = Field(min_length=1, max_length=500)
    audience_specific_cue: str = Field(min_length=1, max_length=500)
    tone: str = Field(min_length=1, max_length=200)
    style_direction: str = Field(min_length=1, max_length=500)
    things_to_avoid: list[str] = Field(min_length=1, max_length=10)
    specificity_reason: str = Field(min_length=1, max_length=700)

    @field_validator("source_url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        """Reject fabricated non-web references while allowing provider-specific URL shapes."""

        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url must be an absolute HTTP(S) URL")
        return value


class SocialIdentityTextOutput(BaseModel):
    """Complete structured response returned by the identity-focused social call."""

    identity_selected: str = Field(default="", max_length=300)
    identity_type_selected: IdentityType | None = None
    candidates: list[SocialIdentityTextCandidate] = Field(min_length=1, max_length=25)
    search_summary: str = Field(min_length=1, max_length=2_000)
    topic_explored: str = Field(default="", max_length=500)
    model: str = "deterministic"


def reasoning_instructions() -> str:
    """Return the provider contract that makes identity preservation non-optional."""

    return (
        "You are a merchandise discovery researcher and targeted novelty-T-shirt creative director. "
        "Use the supplied web search tool to inspect public Reddit and/or X discussions, but treat "
        "the user-supplied identity as a hard audience anchor. Do not replace it with a broad "
        "demographic, invent an identity, or infer sensitive traits. Extract concrete behavior, "
        "friction, contradiction, ritual, or private joke that is recognizably experienced by that "
        "identity. If the identity is not supplied, choose one concrete, non-sensitive identity "
        "from the discussions and classify it as an occupation, role, community, lifestyle, or "
        "other identity; return it in `identity_selected` and `identity_type_selected`. Every "
        "merchandise line and artwork prompt must preserve the identity naturally, "
        "so the target person thinks 'that is literally me' rather than merely seeing a generic joke. "
        "The merchandise line must make sense alone and should sound like a specific person or "
        "relationship making a claim, confession, complaint, or dry observation—not an advertising "
        "slogan, product title, or category label. Use a concrete role-specific duty, tool, setting, "
        "relationship, object, time, or exact action when supported by the source. Use as many words "
        "as needed to make the premise clear; there is no hard length limit. A second clause or "
        "sentence is encouraged when it makes the insider joke legible, but remove unnecessary case "
        "detail and statistics. Do not force an 'I ...' template. Alongside the copy, create a Grok "
        "artwork prompt that renders the exact line prominently and visibly identifies the supplied "
        "identity through one specific cue and one visual joke. Use a bold, high-contrast, limited-"
        "palette novelty-T-shirt graphic, not soft lifestyle photography, generic category imagery, "
        "logos, brands, or extra text. Preserve source URLs and source-specific excerpts. Return only "
        "the requested structured output."
    )


def build_user_prompt(input_model: SocialIdentityTextInput) -> str:
    """Build a provider request that repeats the identity anchor at every important decision."""

    platforms = ", ".join(source.value for source in input_model.sources)
    identity_instruction = (
        "Choose one concrete, non-sensitive identity represented in the discussions before choosing "
        "the behavior. Return it in `identity_selected` and classify it in `identity_type_selected`. "
        "Use only the allowed identity types; do not infer sensitive personal traits."
        if input_model.auto_identity
        else (
            f"Use this supplied identity exactly: {input_model.identity}. "
            f"Its identity type is {input_model.identity_type.value}."
        )
    )
    topic_instruction = (
        "Choose a narrow behavior or topic within this identity before searching. Prefer a distinct "
        "tension, contradiction, absurdity, or private joke; avoid generic routines and broad "
        "identity slogans. Return the chosen topic in `topic_explored`."
        if input_model.auto_topic
        else f"Behavior/topic to investigate within this identity: {input_model.query}"
    )
    identity_context = (
        ""
        if input_model.auto_identity
        else (
            f"Target identity: {input_model.identity}\n"
            f"Identity type: {input_model.identity_type.value}\n"
        )
    )
    return (
        f"{identity_instruction}\n"
        f"{identity_context}"
        f"Search these public platforms: {platforms}.\n"
        f"{topic_instruction}\n"
        f"Return up to {input_model.candidate_count} distinct candidates. Each candidate must include "
        "identity evidence explaining why the source actually supports this identity, then one "
        "specific behavior and friction grounded in that identity. The merchandise text must be "
        "self-explanatory, targeted T-shirt copy: preserve the identity, scene, action, and payoff "
        "without requiring the metadata. Avoid repeating the same identity behavior in different "
        "wording. Also provide an artwork_prompt, visual_punchline, main_visual_metaphor, "
        "audience_specific_cue, tone, style_direction, and things_to_avoid. The visual cue must "
        "make the supplied identity recognizable without relying on a logo, institution, or invented "
        "uniform. Cite one directly relevant source URL per candidate and return the actual topic in "
        "`topic_explored`."
    )


def _source_domain_is_valid(candidate: SocialIdentityTextCandidate) -> bool:
    """Check that a provider citation belongs to the platform it claims to represent."""

    hostname = (urlparse(candidate.source_url).hostname or "").lower()
    if candidate.source_platform == SocialSource.REDDIT:
        return hostname == "reddit.com" or hostname.endswith(".reddit.com")
    return hostname in {"x.com", "twitter.com"} or hostname.endswith((".x.com", ".twitter.com"))


def execute(
    input_model: SocialIdentityTextInput,
    *,
    reasoning_output: SocialIdentityTextOutput | None = None,
    model: str = "deterministic",
) -> SocialIdentityTextOutput:
    """Validate live output or produce an explicit fixture result for local demos."""

    if reasoning_output is not None:
        if len(reasoning_output.candidates) > input_model.candidate_count:
            raise ValueError("Identity-focused provider returned more candidates than configured.")
        selected_identity = (reasoning_output.identity_selected or input_model.identity).strip()
        selected_identity_type = reasoning_output.identity_type_selected or input_model.identity_type
        if not input_model.auto_identity:
            # Manual input is the user's source of truth; provider wording cannot replace it.
            selected_identity = input_model.identity.strip()
            selected_identity_type = input_model.identity_type
        if len(selected_identity) < 2 or selected_identity_type is None:
            raise ValueError(
                "Identity-focused provider must return identity_selected and "
                "identity_type_selected when identity is AI-selected."
            )
        allowed_sources = set(input_model.sources)
        normalized_candidates = []
        for candidate in reasoning_output.candidates:
            if candidate.source_platform not in allowed_sources:
                raise ValueError(
                    "Identity-focused provider returned a candidate from an unrequested source."
                )
            if not _source_domain_is_valid(candidate):
                raise ValueError(
                    f"Identity-focused provider cited {candidate.source_url!r} for "
                    f"{candidate.source_platform.value}; expected that platform domain."
                )
            # Persist one canonical identity label so downstream artwork and UI records do not
            # alternate between harmless provider typography variants.
            normalized_candidates.append(
                candidate.model_copy(
                    update={
                        "identity": selected_identity,
                        "identity_type": selected_identity_type,
                    }
                )
            )
        return reasoning_output.model_copy(
            update={
                "model": model,
                "identity_selected": selected_identity,
                "identity_type_selected": selected_identity_type,
                "topic_explored": reasoning_output.topic_explored or input_model.query,
                "candidates": normalized_candidates,
            }
        )

    source = input_model.sources[0]
    effective_identity = input_model.identity.strip() or "night-shift workers"
    effective_identity_type = input_model.identity_type or IdentityType.OCCUPATION
    effective_query = input_model.query.strip() or (
        "a small daily behavior that reveals how this identity gets through ordinary life"
    )
    candidates = [
        SocialIdentityTextCandidate(
            identity=effective_identity,
            identity_type=effective_identity_type,
            identity_evidence=(
                f"Fixture identity anchor: {effective_identity} ({effective_identity_type.value})."
            ),
            source_platform=source,
            source_url=f"https://fixture.local/{source.value}/identity/{index}",
            source_title=f"Fixture {source.value} identity behavior {index}",
            source_excerpt=f"Fixture discussion about {input_model.identity}: {effective_query}.",
            audience_context=effective_identity,
            behavior=f"{effective_identity} repeatedly describes {effective_query}.",
            friction_or_pressure="The identity-specific routine collides with ordinary daily pressure.",
            artwork_text=(
                f"{effective_identity} has a very specific way of dealing with {effective_query}"
            ),
            artwork_prompt=(
                f"Create a bold targeted T-shirt graphic for {input_model.identity}. Render the exact "
                f"line prominently and show one visual joke about {effective_query}; no logos or extra text."
            ),
            visual_punchline="An ordinary identity-specific workaround is treated like a heroic operating rule.",
            main_visual_metaphor="A small object becomes an exaggerated tool of identity-specific survival.",
            audience_specific_cue=effective_identity,
            tone="dry, personal, and mildly absurd",
            style_direction="Bold limited-palette screen-print with thick outlines and strong type.",
            things_to_avoid=["generic lifestyle imagery", "invented logos", "extra text"],
            specificity_reason="Fixture output only; replace with live source-backed identity evidence.",
        )
        for index in range(1, input_model.candidate_count + 1)
    ]
    return SocialIdentityTextOutput(
        identity_selected=effective_identity,
        identity_type_selected=effective_identity_type,
        candidates=candidates,
        search_summary="Deterministic fixture output; no social platform was queried.",
        topic_explored=effective_query,
        model=model,
    )
