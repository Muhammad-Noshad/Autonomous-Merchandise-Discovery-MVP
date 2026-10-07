"""Behavior-first social discovery with audience identity selected per candidate."""

from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from merchandise_discovery.domain.models.common import IdentityType, SocialSource
from merchandise_discovery.domain.pipelines.social_behavior_text.pipeline import (
    SocialBehaviorTextCandidate,
)


class BehaviorIdentityInput(BaseModel):
    """Social search scope and output bound for one run."""

    sources: list[SocialSource] = Field(min_length=1)
    query: str = Field(default="", max_length=500)
    auto_topic: bool = False
    candidate_count: int = Field(ge=1, le=25)

    @model_validator(mode="after")
    def validate_topic_source(self) -> "BehaviorIdentityInput":
        if not self.auto_topic and len(self.query.strip()) < 3:
            raise ValueError("query must contain at least 3 characters unless auto_topic is enabled")
        return self


class BehaviorIdentityCandidate(SocialBehaviorTextCandidate):
    """One behavior, its best-supported audience, and the merchandise idea for both."""

    identity: str = Field(min_length=2, max_length=300)
    identity_type: IdentityType
    identity_evidence: str = Field(min_length=1, max_length=1_000)


class BehaviorIdentityOutput(BaseModel):
    """Behavior-led candidates, each independently mapped to an evidence-backed identity."""

    candidates: list[BehaviorIdentityCandidate] = Field(min_length=1, max_length=25)
    search_summary: str = Field(min_length=1, max_length=2_000)
    topic_explored: str = Field(default="", max_length=500)
    model: str = "deterministic"

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_run_identity(cls, value: object) -> object:
        """Carry old persisted run-level identity data into candidates when resuming a run."""

        if not isinstance(value, dict) or not value.get("identity_selected"):
            return value

        identity = value["identity_selected"]
        identity_type = value.get("identity_type_selected")
        identity_evidence = value.get("identity_evidence", "Legacy run-level identity evidence.")
        for candidate in value.get("candidates", []):
            if isinstance(candidate, dict):
                candidate.setdefault("identity", identity)
                candidate.setdefault("identity_type", identity_type)
                candidate.setdefault("identity_evidence", identity_evidence)
        return value


def reasoning_instructions() -> str:
    """Define the behavior-first, per-candidate identity and copy requirements."""

    return (
        "You are a social-discussion researcher and targeted novelty-T-shirt creative director. "
        "Use the supplied web search tool to inspect public discussions from the selected Reddit "
        "and/or X domains. First find distinct, concrete behaviors, rituals, frictions, contradictions, "
        "or private jokes in the discussions. Then, independently for each behavior, identify the "
        "specific, non-sensitive audience group most clearly represented by its evidence. Do not "
        "choose one identity for the whole run and force every behavior into it. Do not start from an "
        "identity category and search for a confirming stereotype. Each identity should be a group "
        "a person might recognize themselves as, broad enough to include multiple people, and no "
        "narrower than the evidence supports. Avoid research-report labels and overly specific job "
        "specialties. Different behaviors may map to the same identity when the evidence supports "
        "that; do not force identity variety. For each candidate return its identity, one allowed "
        "identity type, and concise evidence explaining why that group fits this behavior. The "
        "merchandise line must make the audience recognizable through lived details, not by merely "
        "prefixing an identity label. Use natural role, relationship, duty, setting, time, tool, or "
        "insider language where supported. Write clear, personal, context-rich targeted T-shirt copy: "
        "a specific claim, confession, complaint, or dry observation with a concrete action and payoff. "
        "It must make sense without metadata; use as many words as necessary, but avoid case-summary "
        "detail and forced 'I ...' templates. Keep each candidate's `audience_context` specific to "
        "that candidate's identity and behavior. Create an artwork prompt that renders the exact "
        "merchandise line and turns that identity-specific behavior into one bold, high-contrast, "
        "limited-palette T-shirt graphic. Avoid soft lifestyle imagery, generic category props, logos, "
        "brands, and extra text. Preserve source URLs and source-specific excerpts. Return only the "
        "requested structured output."
    )


def build_user_prompt(input_model: BehaviorIdentityInput) -> str:
    """Ask the provider to map each discovered behavior to its own best-supported audience."""

    platforms = ", ".join(source.value for source in input_model.sources)
    behavior_instruction = (
        "Choose a concrete behavior or topic yourself, then search for discussions showing how "
        "people actually experience it. Prefer specific actions, rituals, objects, contradictions, "
        "or social friction over broad trends or abstract problems. Return the explored area in "
        "`topic_explored`."
        if input_model.auto_topic
        else f"Behavior/topic to investigate: {input_model.query}"
    )
    return (
        f"Search these public platforms: {platforms}.\n"
        f"{behavior_instruction}\n"
        f"Return up to {input_model.candidate_count} distinct behavior-led candidates. For each "
        "candidate, first describe one behavior supported by a specific discussion, then assign "
        "the identity group that best fits that behavior's evidence. Do this independently for "
        "each candidate; there is no single run-level target identity. Include candidate-level "
        "`identity`, `identity_type`, and `identity_evidence`. Choose a group that is recognizable "
        "but not narrower than the source supports. Keep candidates distinct by behavior, not by "
        "forcing different identity labels. Also provide source_platform, source_url, source_title, "
        "source_excerpt, audience_context, behavior, friction_or_pressure, artwork_text, "
        "artwork_prompt, visual_punchline, main_visual_metaphor, audience_specific_cue, tone, "
        "style_direction, things_to_avoid, and specificity_reason. Make the merchandise text "
        "understandable on its own and let the audience emerge naturally from its lived details. "
        "Return the behavior or topic actually explored in `topic_explored` and a concise "
        "`search_summary`."
    )


def execute(
    input_model: BehaviorIdentityInput,
    *,
    reasoning_output: BehaviorIdentityOutput | None = None,
    model: str = "deterministic",
) -> BehaviorIdentityOutput:
    """Validate provider source scope, or return visibly marked fixture data."""

    if reasoning_output is None:
        topic = input_model.query.strip() or "people managing an overloaded everyday routine"
        candidates = [
            BehaviorIdentityCandidate(
                identity=f"People dealing with {topic}",
                identity_type=IdentityType.OTHER,
                identity_evidence="Fixture only; no social platform was queried.",
                source_platform=input_model.sources[0],
                source_url=f"https://fixture.local/{input_model.sources[0].value}/behavior/{index}",
                source_title=f"Fixture behavior {index}",
                source_excerpt=f"Fixture discussion about {topic}.",
                audience_context=f"People dealing with {topic}",
                behavior=f"People repeatedly deal with {topic}.",
                friction_or_pressure="The routine keeps colliding with ordinary daily demands.",
                artwork_text=f"Still making {topic} work",
                artwork_prompt=(
                    f'Create a bold, print-ready T-shirt graphic for "Still making {topic} work". '
                    "Show one specific visual joke about this audience and behavior."
                ),
                visual_punchline="A small daily workaround is treated like a heroic operation.",
                main_visual_metaphor="An everyday tool becomes an overworked control panel.",
                audience_specific_cue=f"People dealing with {topic}",
                tone="dry and self-aware",
                style_direction="High-contrast, limited-palette novelty T-shirt illustration.",
                things_to_avoid=["generic category imagery", "soft lifestyle photography", "extra text"],
                specificity_reason="Fixture output only; replace with source-backed live research.",
            )
            for index in range(1, input_model.candidate_count + 1)
        ]
        return BehaviorIdentityOutput(
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

    return reasoning_output.model_copy(
        update={
            "topic_explored": reasoning_output.topic_explored or input_model.query,
            "model": model,
        }
    )
