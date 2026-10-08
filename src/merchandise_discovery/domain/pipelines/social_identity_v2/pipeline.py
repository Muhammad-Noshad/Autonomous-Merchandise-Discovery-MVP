"""Prompt-focused identity pipeline used for the second social A/B variant.

The V2 experiment intentionally keeps the same data contract and one-call execution shape as the
existing identity-focused pipeline. Its only production difference is the prompt strategy: the
provider must turn source-backed identity signals directly into self-explanatory merchandise copy.
Keeping the contract shared makes output quality attributable to prompting rather than a second
research pass, new persistence model, or extra provider call.
"""

from merchandise_discovery.domain.models.common import identity_type_guidance
from merchandise_discovery.domain.pipelines.social_identity_focused.pipeline import (
    SocialIdentityTextCandidate as SocialIdentityV2Candidate,
)
from merchandise_discovery.domain.pipelines.social_identity_focused.pipeline import (
    SocialIdentityTextInput as SocialIdentityV2Input,
)
from merchandise_discovery.domain.pipelines.social_identity_focused.pipeline import (
    SocialIdentityTextOutput as SocialIdentityV2Output,
)
from merchandise_discovery.domain.pipelines.social_identity_focused.pipeline import (
    execute as _execute_identity_pipeline,
)

__all__ = [
    "SocialIdentityV2Candidate",
    "SocialIdentityV2Input",
    "SocialIdentityV2Output",
    "build_user_prompt",
    "execute",
    "reasoning_instructions",
]


def reasoning_instructions() -> str:
    """Return the prompt-only identity strategy for the controlled A/B variant."""

    return (
        "You are a merchandise discovery researcher and targeted novelty-T-shirt creative director. "
        "Use the supplied web search tool to inspect public Reddit and/or X discussions, but treat "
        "the selected identity as a hard audience anchor. Extract a concrete behavior, ritual, "
        "artifact, phrase, contradiction, or private joke that this identity would recognize from "
        "their own life. Do not write about the identity as a broad category. Every merchandise line "
        "must be self-explanatory when read by itself and should make the target person think 'that is "
        "literally me'. Apply a blind-recognition test before returning each line: if the identity "
        "metadata were hidden, a reader should still be able to identify the intended audience from "
        "the lived detail. Make the identity recognizable through natural first-person language, a "
        "relationship, setting, schedule, duty, or insider phrase—not by pasting the audience label "
        "in front of the joke. Never format merchandise text as 'IDENTITY: slogan', a category title, "
        "or an all-caps audience heading. The actual merchandise text must contain at least one "
        "natural identity cue, or two unmistakable contextual cues that identify the audience "
        "together. For an occupation, a natural possessive relationship to the people they serve, "
        "teach, supervise, treat, or work alongside can be useful when supported by the source, but "
        "do not force the same role phrase into every candidate. For a compound identity, preserve every defining "
        "dimension in natural language: for example, 'night-shift remote workers' needs both a "
        "night-work cue and a remote, home, laptop, or online-work cue. Do not substitute a "
        "warehouse, hospital, delivery, or office worker unless that setting belongs to the selected "
        "identity. A standalone shared object must be connected naturally "
        "to the target person's responsibility, duty, or conflict. State the identity naturally in the line when that improves recognition, or "
        "use an unmistakable role-specific marker, duty, tool, setting, relationship, or insider "
        "phrase. The line must communicate the situation, concrete action, and consequence or joke "
        "without requiring the behavior, friction, or specificity metadata. Use as many words as "
        "needed for clarity; do not force every line into an 'I ...' template and do not shorten a "
        "specific joke into a generic slogan. Prefer the style of targeted novelty T-shirts: blunt, "
        "personal, context-rich, slightly provocative, and understandable to an outsider. Avoid "
        "category labels, generic workplace stress, broad motivational statements, and copy that "
        "could describe an adjacent identity. Alongside each line, create a Grok artwork prompt that "
        "preserves the same identity-specific behavior, setting, and visual joke. Use bold, high-"
        "contrast, limited-palette, print-ready artwork rather than soft lifestyle imagery. Do not "
        "invent logos, brands, institutions, uniforms, or extra text. Preserve source URLs and "
        "source-specific excerpts. Return only the requested structured output."
    )


def build_user_prompt(input_model: SocialIdentityV2Input) -> str:
    """Build the V2 request while reusing the original identity pipeline's input contract."""

    platforms = ", ".join(source.value for source in input_model.sources)
    identity_instruction = (
        "Choose one concrete, non-sensitive identity represented in the discussions before choosing "
        "the behavior. Internally compare several concrete identities across the available identity "
        "types, then choose the most distinctive one with repeated "
        "source evidence rather than the most familiar profession. Name it as a natural human "
        "identity label that a person would actually use for themselves, not as a bureaucratic "
        "industry description or research segment. Return it in `identity_selected` "
        f"and classify it in `identity_type_selected` using this taxonomy: {identity_type_guidance()}. "
        "Do not "
        "infer sensitive personal traits."
        if input_model.auto_identity
        else (
            f"Use this supplied identity exactly: {input_model.identity}. "
            f"Its identity type is {input_model.identity_type.value}."
        )
    )
    topic_instruction = (
        "Choose a narrow behavior or topic within this identity before searching. Prefer a distinct "
        "lived situation: a concrete incident, object, ritual, insider phrase, contradiction, or "
        "private joke that this audience would recognize from their own life. Translate any "
        "institutional or system-level problem into what the person actually does, sees, handles, "
        "says, or complains about. Avoid generic routines, broad identity slogans, hidden operational "
        "consequences, systemic challenges, industry trends, and research-report phrasing. Return the "
        "chosen topic in `topic_explored` as a human situation, not a report heading."
        if input_model.auto_topic
        else f"Behavior/topic to investigate within this identity: {input_model.query}"
    )
    diversity_instruction = (
        "Prefer a specific, underrepresented audience supported by repeated evidence. Do not default "
        "to a familiar healthcare, education, or office profession merely because it has many search "
        "results. Recent identities to avoid repeating unless materially different: "
        + ", ".join(input_model.recent_identity_selections)
        + ".\n"
        if input_model.auto_identity
        else ""
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
        f"{diversity_instruction}"
        f"{topic_instruction}\n"
        f"Return up to {input_model.candidate_count} distinct candidates. Each candidate must be "
        "source-backed and identity-recognizable without the reader seeing any metadata. The actual "
        "merchandise text must communicate the concrete situation, action, and payoff through natural "
        "lived detail and contain at least one natural identity cue, or two strong contextual cues "
        "working together. Use a role-specific phrase, object, time, setting, relationship, or duty "
        "when the source supports it. If the text contains only a shared object or setting, connect it "
        "naturally to the target person's relationship with that object. If the selected identity has "
        "multiple defining words, preserve those dimensions rather than generalizing to a nearby "
        "audience. Do not return lines that are merely a prefixed audience label, category title, or "
        "a vague statement about being tired, busy, proud, calm, or stressed. Do "
        "not generate several versions of the same behavior. Include "
        "identity evidence, behavior, friction_or_pressure, artwork_prompt, visual_punchline, "
        "main_visual_metaphor, audience_specific_cue, tone, style_direction, and things_to_avoid. "
        "The artwork prompt must render the exact merchandise text and make the identity-specific "
        "joke visible without generic category imagery. Cite one directly relevant source URL per "
        "candidate and return the actual topic in `topic_explored`."
    )


def execute(
    input_model: SocialIdentityV2Input,
    *,
    reasoning_output: SocialIdentityV2Output | None = None,
    model: str = "deterministic",
) -> SocialIdentityV2Output:
    """Reuse the original identity validation and fixture behavior for a fair A/B comparison."""

    return _execute_identity_pipeline(
        input_model,
        reasoning_output=reasoning_output,
        model=model,
    )
