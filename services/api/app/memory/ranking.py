"""Composite memory ranking (docs/DESIGN.md §5.3).

score = w_sim·similarity + w_imp·importance + w_rec·recency_decay
      + w_acc·access_freq + w_type·type_priority − w_red·redundancy(MMR)

Weights are tuned via the eval harness (§6.6), not hard-coded forever.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RankWeights:
    similarity: float = 0.45
    importance: float = 0.20
    recency: float = 0.15
    access: float = 0.10
    type_priority: float = 0.10


# Per-type recency half-life (days). Active goals/projects do not decay.
TYPE_HALF_LIFE_DAYS = {
    "episodic": 30.0,
    "semantic": 365.0,
    "insight": 180.0,
    "message": 14.0,
}


def score_memory(*args, **kwargs) -> float:  # noqa: ANN002, ANN003
    """TODO: implement composite scoring + MMR diversity penalty."""
    raise NotImplementedError
