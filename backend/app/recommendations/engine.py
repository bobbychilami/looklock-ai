"""Deterministic outfit recommendation.

No model is called here, and none should be: the whole point of this module is
that the same catalogue and the same answers always produce the same three looks,
in the same order, with the same reasoning. That makes the feature testable and
makes a surprising result a bug rather than a mood.

Scoring has four parts, each a 0..1 ratio, combined with fixed weights:

* **occasion** - the share of wearable pieces whose `occasions` include the
  requested occasion.
* **style** - the same share, using `styles`.
* **budget** - how well the look spends the budget without exceeding it. Under
  budget scores by utilisation, so a look that actually uses the budget beats an
  identical cheaper one; over budget is penalised and only reached when the
  catalogue cannot fill three looks otherwise.
* **completeness** - whether footwear and an accessory are included. Required
  slots are top and bottom, so this is a genuine ranking signal and it is also
  what lets a small budget still produce a wearable outfit.

When the catalogue cannot supply three looks inside the budget, constraints are
relaxed in a fixed, stated order rather than silently.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from itertools import product as cartesian

from app.catalog.product import (
    COMPLETENESS_WEIGHTS,
    Occasion,
    Product,
)
from app.recommendations.schemas import (
    LookRecommendation,
    LookScore,
    RecommendationRequest,
    RecommendationResponse,
    ScoredProduct,
)

#: Relative importance of each score. Must sum to 1.0.
WEIGHTS: dict[str, float] = {
    "occasion": 0.35,
    "style": 0.25,
    "budget": 0.25,
    "completeness": 0.15,
}

#: How many looks to return. A product requirement, not a preference.
LOOK_COUNT = 3

#: Maximum number of shared product ids between two looks. Keeps the three
#: suggestions genuinely different outfits rather than three variations on one.
IDEAL_MAX_SHARED = 1
FALLBACK_MAX_SHARED = 2

#: Ceiling for the budget component of an over-budget look. Strictly below 1.0
#: so satisfying the budget always outranks exceeding it.
OVER_BUDGET_FLOOR = 0.45

_MAX_COMPLETENESS = sum(COMPLETENESS_WEIGHTS.values())


class InsufficientInventoryError(LookupError):
    """Raised when the catalogue cannot form even one wearable outfit."""


@dataclass(frozen=True)
class Candidate:
    """One possible outfit, before scoring."""

    top: Product
    bottom: Product
    footwear: Product | None
    accessory: Product | None

    @property
    def items(self) -> tuple[Product, ...]:
        found = [self.top, self.bottom]
        if self.footwear is not None:
            found.append(self.footwear)
        if self.accessory is not None:
            found.append(self.accessory)
        return tuple(found)

    @property
    def wearable(self) -> tuple[Product, ...]:
        """Pieces a person actually wears. Accessories do not count for fit."""
        found = [self.top, self.bottom]
        if self.footwear is not None:
            found.append(self.footwear)
        return tuple(found)

    @property
    def total_price_inr(self) -> int:
        return sum(item.price_inr for item in self.items)

    @property
    def key(self) -> str:
        """Stable identity, used for deterministic tie-breaking."""
        parts = [self.top.product_id, self.bottom.product_id]
        if self.footwear is not None:
            parts.append(self.footwear.product_id)
        if self.accessory is not None:
            parts.append(self.accessory.product_id)
        return "|".join(parts)

    @property
    def hero(self) -> Product:
        """The garment sent as the try-on reference.

        V4.0 accepts one reference garment per request, so the top piece anchors
        the look. A future full-body pass would instead use a `full_body` asset.
        """
        return self.top


def build_candidates(
    catalogue: Sequence[Product], *, occasion: Occasion | None = None
) -> tuple[Candidate, ...]:
    """Every top x bottom x optional-footwear x optional-accessory outfit.

    The full cross product is cheap at this catalogue size (a few thousand rows)
    and avoids the arbitrariness of hand-curated outfit lists: ranking decides
    what a shopper sees, not the order someone happened to write the seed down.

    When an occasion is given, the accessory pool is narrowed to pieces tagged
    for it. Accessories are deliberately excluded from the occasion and style
    *scores* - a belt does not change how well a fit suits someone - so without
    this filter a wedding look could quietly contain an interview-only belt.
    """
    tops = [item for item in catalogue if item.slot == "top"]
    bottoms = [item for item in catalogue if item.slot == "bottom"]
    if not tops or not bottoms:
        raise InsufficientInventoryError(
            "The catalogue has no "
            f"{'tops' if not tops else 'bottoms'} to build an outfit from. "
            "At least one top and one bottom are required."
        )

    footwear: list[Product | None] = [None, *[i for i in catalogue if i.slot == "footwear"]]
    all_accessories = [i for i in catalogue if i.slot == "accessory"]
    if occasion is not None:
        fitting = [i for i in all_accessories if i.matches_occasion(occasion)]
        # Never let the filter empty the pool outright; an unrelated accessory is
        # better than none, and the notice already reports weak occasion matches.
        all_accessories = fitting or all_accessories
    accessories: list[Product | None] = [None, *all_accessories]

    return tuple(
        Candidate(top=top, bottom=bottom, footwear=shoe, accessory=extra)
        for top, bottom, shoe, extra in cartesian(tops, bottoms, footwear, accessories)
    )


def _share(matches: Iterable[bool]) -> float:
    values = list(matches)
    if not values:
        return 0.0
    return sum(values) / len(values)


def _budget_score(total: int, budget: int) -> float:
    """How well a look spends the budget.

    Under budget the score is utilisation, so spending more of the budget is
    better - but never at the cost of exceeding it.

    Over budget the score has to stay *monotonic* rather than saturate. An
    earlier version clamped at zero, which made every large overage tie exactly
    and left the tie-break free to pick the most expensive look in the catalogue.
    `OVER_BUDGET_FLOOR / (1 + overshoot)` keeps a real ordering all the way down,
    so cheaper-but-still-over always loses to nothing and beats something worse,
    while occasion and style - the signals a shopper actually chose - stay in
    charge of the ranking.
    """
    if budget <= 0:
        return 1.0 if total <= 0 else 0.0
    if total <= budget:
        return max(0.0, min(1.0, total / budget))
    overshoot = (total - budget) / budget
    return OVER_BUDGET_FLOOR / (1.0 + overshoot)


def score_candidate(candidate: Candidate, request: RecommendationRequest) -> LookScore:
    occasion_share = _share(
        item.matches_occasion(request.occasion) for item in candidate.wearable
    )
    style_share = _share(item.matches_style(request.style) for item in candidate.wearable)
    budget_share = _budget_score(candidate.total_price_inr, request.budget_inr)
    completeness = (
        sum(
            COMPLETENESS_WEIGHTS[item.slot]
            for item in candidate.items
            if item.slot in COMPLETENESS_WEIGHTS
        )
        / _MAX_COMPLETENESS
    )

    total = (
        WEIGHTS["occasion"] * occasion_share
        + WEIGHTS["style"] * style_share
        + WEIGHTS["budget"] * budget_share
        + WEIGHTS["completeness"] * completeness
    )
    return LookScore(
        occasion=round(occasion_share, 4),
        style=round(style_share, 4),
        budget=round(budget_share, 4),
        completeness=round(completeness, 4),
        total=round(min(1.0, max(0.0, total)), 4),
    )


def _reasons(
    candidate: Candidate, request: RecommendationRequest
) -> tuple[str, ...]:
    """Plain-language justification, built only from the products' own attributes."""
    reasons: list[str] = []
    wearable = candidate.wearable

    occasion_hits = sum(1 for item in wearable if item.matches_occasion(request.occasion))
    if occasion_hits == len(wearable):
        reasons.append(f"Every piece is styled for {request.occasion.lower()}")
    else:
        reasons.append(
            f"{occasion_hits} of {len(wearable)} pieces are styled for "
            f"{request.occasion.lower()}"
        )

    style_hits = sum(1 for item in wearable if item.matches_style(request.style))
    if style_hits == len(wearable):
        reasons.append(f"Consistently {request.style.lower()} throughout")
    else:
        reasons.append(
            f"{style_hits} of {len(wearable)} pieces read as {request.style.lower()}"
        )

    total = candidate.total_price_inr
    budget = request.budget_inr
    if total <= budget:
        reasons.append(f"₹{total:,} of your ₹{budget:,} budget")
    else:
        reasons.append(f"₹{total:,} - ₹{total - budget:,} over your budget")

    if candidate.footwear is not None and candidate.accessory is not None:
        reasons.append("Complete look, footwear and finishing piece included")
    elif candidate.footwear is not None:
        reasons.append("Includes footwear")
    return tuple(reasons)


def _shared_ids(chosen: Sequence[Candidate], candidate: Candidate) -> int:
    picked = {item.product_id for look in chosen for item in look.items}
    return len(picked & {item.product_id for item in candidate.items})


def _select(
    ranked: Sequence[tuple[Candidate, LookScore]], limit: int
) -> tuple[list[Candidate], list[LookScore]]:
    """Greedy pick with a diversity constraint, loosened only if necessary.

    Returns the fullest selection any pass achieved rather than nothing when the
    limit is unreachable. A catalogue with a single valid outfit must come back
    as that one look with a notice, not as an error.
    """
    best: tuple[list[Candidate], list[LookScore]] = ([], [])
    for max_shared in (IDEAL_MAX_SHARED, FALLBACK_MAX_SHARED, len(ranked) or 1):
        chosen: list[Candidate] = []
        scores: list[LookScore] = []
        for candidate, score in ranked:
            if _shared_ids(chosen, candidate) <= max_shared:
                chosen.append(candidate)
                scores.append(score)
                if len(chosen) == limit:
                    return chosen, scores
        if len(chosen) > len(best[0]):
            best = (chosen, scores)
    return best


def recommend(
    request: RecommendationRequest,
    catalogue: Sequence[Product],
    *,
    image_url_for: Callable[[Product], str],
) -> RecommendationResponse:
    """Return exactly three ranked looks, or the best the catalogue allows."""
    candidates = build_candidates(catalogue, occasion=request.occasion)
    scored = [(candidate, score_candidate(candidate, request)) for candidate in candidates]
    # Deterministic: best score first, then a stable key so equal scores never
    # reorder between runs or between processes.
    scored.sort(key=lambda row: (-row[1].total, row[0].key))

    in_budget = [row for row in scored if row[0].total_price_inr <= request.budget_inr]
    if len(in_budget) >= LOOK_COUNT:
        pool = in_budget
    else:
        over = [row for row in scored if row[0].total_price_inr > request.budget_inr]
        # When the budget cannot be met, `_budget_score` being monotonic means the
        # existing score order already puts the closest match first among looks
        # that are otherwise equally good on occasion and style - no re-sorting
        # needed. If nothing exceeds the budget at all, the catalogue is simply
        # too small to make three looks and `_notice` reports that instead.
        pool = over or in_budget

    chosen, scores = _select(pool, LOOK_COUNT)
    if not chosen:
        raise InsufficientInventoryError(
            "The catalogue is too small to build a complete look from a top and a bottom."
        )

    looks = tuple(
        LookRecommendation(
            look_id=f"look-{index + 1}",
            rank=index + 1,
            total_price_inr=candidate.total_price_inr,
            hero_product_id=candidate.hero.product_id,
            items=tuple(
                ScoredProduct.from_product(
                    item,
                    image_url=image_url_for(item),
                    occasion=request.occasion,
                    style=request.style,
                )
                for item in candidate.items
            ),
            score=score,
            reasons=_reasons(candidate, request),
        )
        for index, (candidate, score) in enumerate(zip(chosen, scores, strict=True))
    )

    over_budget = [look for look in looks if look.total_price_inr > request.budget_inr]
    relaxed: tuple[str, ...] = ("budget",) if over_budget else ()
    return RecommendationResponse(
        occasion=request.occasion,
        style=request.style,
        budget_inr=request.budget_inr,
        looks=looks,
        notice=_notice(looks, request, relaxed),
        relaxed_constraints=relaxed,
    )


def _notice(
    looks: Sequence[LookRecommendation],
    request: RecommendationRequest,
    relaxed: Sequence[str],
) -> str | None:
    parts: list[str] = []

    if len(looks) < LOOK_COUNT:
        parts.append(
            f"This catalogue only supports {len(looks)} complete "
            f"{'look' if len(looks) == 1 else 'looks'} for these answers"
        )

    if "budget" in relaxed:
        over = [look for look in looks if look.total_price_inr > request.budget_inr]
        if over:
            cheapest = min(look.total_price_inr for look in over)
            parts.append(
                f"we could not fill three looks within ₹{request.budget_inr:,}, "
                f"so these start at ₹{cheapest:,}"
            )
        else:
            parts.append(f"fewer than three looks fit within ₹{request.budget_inr:,}")

    if not parts:
        return None
    sentence = "; ".join(parts)
    return sentence[0].upper() + sentence[1:]
