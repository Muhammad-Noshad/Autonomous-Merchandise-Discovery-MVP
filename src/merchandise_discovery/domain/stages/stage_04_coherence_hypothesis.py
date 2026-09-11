"""Stage 4: score coherence and form recognizable experience hypotheses."""

from pydantic import BaseModel

from merchandise_discovery.domain.models.artifacts import IdentityIntersection


class CoherenceInput(BaseModel):
    """Intersections awaiting deterministic experience reasoning."""

    intersections: list[IdentityIntersection]


class CoherenceOutput(BaseModel):
    """Intersections enriched with hypotheses and reproducible coherence scores."""

    intersections: list[IdentityIntersection]


_HYPOTHESIS_TEMPLATES = {
    "care": "A care-heavy audience may use this combination to express responsibility with warmth.",
    "decompression": "This combination points to a recognizable ritual for decompressing after pressure.",
    "focus": "This combination may express the tension between protecting focus and staying connected.",
    "humor": "This combination creates room for an inside joke about a familiar everyday struggle.",
    "ritual": "This combination centers on a repeatable ritual that makes small progress visible.",
}


def execute(input_data: CoherenceInput) -> CoherenceOutput:
    """Assign a transparent score from shared affinity tags and combination structure."""

    scored: list[IdentityIntersection] = []
    for intersection in input_data.intersections:
        tags = [str(tag) for tag in intersection.metadata.get("shared_tags", [])]
        primary_tag = tags[0] if tags else ""
        score = min(
            10.0,
            4.0 + len(tags) * 1.25 + (0.75 if len(intersection.identities) == 3 else 0),
        )
        hypothesis = _HYPOTHESIS_TEMPLATES.get(
            primary_tag,
            "This combination needs stronger shared signals before it is ready for research.",
        )
        scored.append(
            intersection.model_copy(
                update={
                    "coherence_score": round(score, 2),
                    "experience_hypotheses": [hypothesis],
                    "metadata": {
                        **intersection.metadata,
                        "coherence_rationale": (
                            f"{len(tags)} shared affinity tag(s); "
                            f"{len(intersection.identities)} identity dimensions."
                        ),
                    },
                }
            )
        )
    return CoherenceOutput(intersections=scored)
