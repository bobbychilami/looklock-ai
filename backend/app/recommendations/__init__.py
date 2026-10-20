"""Deterministic outfit recommendation for LOOKLOCK."""

from app.recommendations.engine import (
    LOOK_COUNT,
    WEIGHTS,
    Candidate,
    InsufficientInventoryError,
    build_candidates,
    recommend,
    score_candidate,
)
from app.recommendations.naming import (
    LookVisual,
    VisualLayer,
    build_visual,
    name_looks,
)
from app.recommendations.schemas import (
    BUDGET_PRESETS_INR,
    MAX_BUDGET_INR,
    MIN_BUDGET_INR,
    OPEN_BUDGET_CEILING_INR,
    LookRecommendation,
    LookScore,
    RecommendationRequest,
    RecommendationResponse,
    ScoredProduct,
)

__all__ = [
    "BUDGET_PRESETS_INR",
    "LOOK_COUNT",
    "MAX_BUDGET_INR",
    "MIN_BUDGET_INR",
    "OPEN_BUDGET_CEILING_INR",
    "WEIGHTS",
    "Candidate",
    "InsufficientInventoryError",
    "LookRecommendation",
    "LookScore",
    "LookVisual",
    "RecommendationRequest",
    "RecommendationResponse",
    "ScoredProduct",
    "VisualLayer",
    "build_candidates",
    "build_visual",
    "name_looks",
    "recommend",
    "score_candidate",
]
