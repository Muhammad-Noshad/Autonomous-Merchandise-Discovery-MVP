"""Behavior-first, identity-grounded social-to-merchandise pipeline contract.

Unlike the identity-first variants, this pipeline first finds a specific behavior in public
discussions and only then identifies the audience most closely associated with that behavior.
It makes one structured reasoning call; Stage 2 reuses the existing social artwork handoff.
"""

from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from merchandise_discovery.domain.models.common import IdentityType, SocialSource
from merchandise_discovery.domain.pipelines.social_behavior_text.pipeline import (
    SocialBehaviorTextCandidate,
)


class BehaviorIdentityInput(BaseModel):
    """Social search scope, optional identity constraint, and output bound for one run."""

    sources: list[SocialSource] = Field(min_length=1)
    identity: str = Field(default="", max_length=300)
    identity_type: IdentityType | None = None
    auto_identity: bool = False
    query: str = Field(default="", max_length=500)
    auto_topic: bool = False
    candidate_count: int = Field(ge=1, le=25)
    recent_identity_selections: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("identity")
    @classmethod
    def strip_identity(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_manual_inputs(self) -> "BehaviorIdentityInput":
        if not self.auto_identity and len(self.identity) < 2:
            raise ValueError("identity must contain at least 2 characters unless auto_identity is enabled")
        if not self.auto_identity and self.identity_type is None:
            raise ValueError("identity_type is required unless auto_identity is enabled")
        if not self.auto_topic and len(self.query.strip()) < 3:
            raise ValueError("query must contain at least 3 characters unless auto_topic is enabled")
        return self


class BehaviorIdentityOutput(BaseModel):
    """One run-level audience identity and its behavior-led merchandise candidates."""

    identity_selected: str = Field(min_length=2, max_length=300)
    identity_type_selected: IdentityType
    identity_evidence: str = Field(min_length=1, max_length=1_000)
    candidates: list[SocialBehaviorTextCandidate] = Field(min_length=1, max_length=25)
    search_summary: str = Field(min_length=1, max_length=2_000)
    topic_explored: str = Field(default="", max_length=500)
    model: str = "deterministic"


def reasoning_instructions() -> str:
    """Define the evidence order and creative requirements for the single provider call."""

    return (
        "You are a social-discussion researcher and targeted novelty-T-shirt creative director. "
        "Use the supplied web search tool to inspect public discussions from the selected Reddit "
        "and/or X domains. Follow this order: first find a concrete, repeated behavior, ritual, "
        "friction, contradiction, or private joke in the discussions; then determine which one "
        "specific, non-sensitive audience identity most clearly experiences that behavior. Do not "
        "start from an identity category and search for a confirming stereotype. The selected "
        "identity must be supported by the actual discussion evidence, recognizable as a group a "
        "person might call themselves, and broad enough to include multiple people rather than one "
        "individual. Avoid overly narrow job specialties or research-report labels. For a supplied "
        "identity, keep it as the target audience while still finding a behavior-led angle; do not "
        "replace it with an adjacent group. Return one run-level identity and explain the source "
        "evidence for that choice. Every merchandise line must communicate a lived situation that "
        "makes the target identity recognizable without merely prefixing its label. Use natural role, "
        "relationship, duty, setting, time, tool, or insider language where supported. Write clear, "
        "personal, context-rich targeted T-shirt copy: a specific claim, confession, complaint, or "
        "dry observation with a concrete action and payoff. It must make sense without metadata; use "
        "as many words as necessary, but avoid case-summary detail and forced 'I ...' templates. "
        "Keep each candidate tied to the selected identity, and make its `audience_context` state "
        "the identity plus the relevant behavior. Create an artwork prompt that renders the exact "
        "merchandise line and turns the identity-specific behavior into one bold, high-contrast, "
        "limited-palette T-shirt graphic. Avoid soft lifestyle imagery, generic category props, "
        "logos, brands, and extra text. Preserve source URLs and source-specific excerpts. Return "
        "only the requested structured output."
    )


def build_user_prompt(input_model: BehaviorIdentityInput) -> str:
    """Ask the model to identify the behavior before naming its clearest audience."""

    platforms = ", ".join(source.value for source in input_model.sources)
    behavior_instruction = (
        "Choose a concrete behavior or topic yourself, then search for discussions that show how "
        "people actually experience it. Prefer a specific action, ritual, object, contradiction, "
        "or social friction over a broad trend or abstract problem. Return the behavior in "
        "`topic_explored`."
        if input_model.auto_topic
        else f"Behavior/topic to investigate: {input_model.query}"
    )
    identity_instruction = (
        "After you have established the behavior from the discussions, compare the identities "
        "clearly represented in that evidence and select one run-level identity: the audience that "
        "owns or experiences "
        "it most distinctly. Do not choose the easiest or most familiar profession. Avoid repeating "
        "these recent AI-selected identities unless the evidence gives a materially different angle: "
        + (", ".join(input_model.recent_identity_selections) or "none recorded")
        + ". Return the identity in `identity_selected`, its allowed type in "
        "`identity_type_selected`, and the evidence in `identity_evidence`."
        if input_model.auto_identity
        else (
            f"The target identity is {input_model.identity!r} "
            f"({input_model.identity_type.value}). First identify the behavior in the discussions, "
            "then explain how the evidence connects that behavior to this audience. Do not replace "
            "the supplied identity. Return it in `identity_selected` and `identity_type_selected`, "
            "and summarize its source grounding in `identity_evidence`."
        )
    )
    return (
        f"Search these public platforms: {platforms}.\n"
        f"{behavior_instruction}\n"
        f"{identity_instruction}\n"
        f"Return up to {input_model.candidate_count} distinct candidates, all for that single "
        "run-level identity. Each candidate must cite a directly relevant source and provide a "
        "source-specific excerpt, audience_context, behavior, friction_or_pressure, artwork_text, "
        "artwork_prompt, visual_punchline, main_visual_metaphor, audience_specific_cue, tone, "
        "style_direction, things_to_avoid, and specificity_reason. Keep the copy recognizable to "
        "the selected audience through the lived detail, not an identity-label heading. Avoid "
        "repeating the same joke in different words. Return the actual behavior investigated in "
        "`topic_explored` and a concise account of the search in `search_summary`."
    )


def execute(
    input_model: BehaviorIdentityInput,
    *,
    reasoning_output: BehaviorIdentityOutput | None = None,
    model: str = "deterministic",
) -> BehaviorIdentityOutput:
    """Validate provider source scope and preserve explicitly supplied audience identity."""

    if reasoning_output is None:
        identity = input_model.identity or "Everyday problem-solvers"
        identity_type = input_model.identity_type or IdentityType.OTHER
        topic = input_model.query.strip() or "people managing an overloaded everyday routine"
        candidates = [
            SocialBehaviorTextCandidate(
                source_platform=input_model.sources[0],
                source_url=f"https://fixture.local/{input_model.sources[0].value}/behavior/{index}",
                source_title=f"Fixture behavior {index}",
                source_excerpt=f"Fixture discussion about {topic}.",
                audience_context=f"{identity} dealing with {topic}",
                behavior=f"{identity} repeatedly deal with {topic}.",
                friction_or_pressure="The routine keeps colliding with ordinary daily demands.",
                artwork_text=f"{identity}: still making {topic} work",
                artwork_prompt=(
                    f'Create a bold, print-ready T-shirt graphic for "{identity}: still making '
                    f'{topic} work". Show one specific visual joke about this audience and behavior.'
                ),
                visual_punchline="A small daily workaround is treated like a heroic operation.",
                main_visual_metaphor="An everyday tool becomes an overworked control panel.",
                audience_specific_cue=identity,
                tone="dry and self-aware",
                style_direction="High-contrast, limited-palette novelty T-shirt illustration.",
                things_to_avoid=["generic category imagery", "soft lifestyle photography", "extra text"],
                specificity_reason="Fixture output only; replace with source-backed live research.",
            )
            for index in range(1, input_model.candidate_count + 1)
        ]
        return BehaviorIdentityOutput(
            identity_selected=identity,
            identity_type_selected=identity_type,
            identity_evidence="Fixture identity; no social platform was queried.",
            candidates=candidates,
            search_summary="Deterministic fixture output; no social platform was queried.",
            topic_explored=topic,
            model=model,
        )
    if len(reasoning_output.candidates) > input_model.candidate_count:
        raise ValueError("Provider returned more candidates than the configured limit.")

    for candidate in reasoning_output.candidates:
        if candidate.source_platform not in input_model.sources:
            raise ValueError(
                f"Provider returned an unrequested source platform: {candidate.source_platform.value}."
            )
        hostname = (urlparse(candidate.source_url).hostname or "").lower()
        if candidate.source_platform == SocialSource.REDDIT:
            valid_domain = hostname == "reddit.com" or hostname.endswith(".reddit.com")
        else:
            valid_domain = hostname in {"x.com", "twitter.com"} or hostname.endswith(
                (".x.com", ".twitter.com")
            )
        if not valid_domain:
            raise ValueError(
                f"Provider cited {candidate.source_url!r} for {candidate.source_platform.value}; "
                "expected the selected platform domain."
            )

    identity = reasoning_output.identity_selected
    identity_type = reasoning_output.identity_type_selected
    if not input_model.auto_identity:
        identity = input_model.identity
        identity_type = input_model.identity_type

    return reasoning_output.model_copy(
        update={
            "identity_selected": identity,
            "identity_type_selected": identity_type,
            "topic_explored": reasoning_output.topic_explored or input_model.query,
            "model": model,
        }
    )
