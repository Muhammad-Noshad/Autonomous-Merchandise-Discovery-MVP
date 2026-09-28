"""Shared artwork boundary for the prompt-focused identity A/B variant.

Stage 2 is deliberately identical to the existing identity-focused pipeline. Reusing its input
mapping, prompt compiler, stable identifiers, provider call, and storage behavior ensures that the
A/B test changes Stage 1 prompting only; artwork quality is not confounded by a second renderer.
"""

from merchandise_discovery.domain.pipelines.social_identity_focused.artwork import (
    IdentityArtworkInput as IdentityV2ArtworkInput,
)
from merchandise_discovery.domain.pipelines.social_identity_focused.artwork import (
    execute,
)

__all__ = ["IdentityV2ArtworkInput", "execute"]
