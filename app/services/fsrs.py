"""
FSRS-5 spaced-repetition scheduling algorithm.

Pure functions only — no DB access, no HTTP.  Call `schedule()` with the
current card state and the user's rating; it returns the updated state.
The router is responsible for persisting the result.

Rating scale:
    1 = Again  (complete blank / wrong)
    2 = Hard   (correct but very difficult)
    3 = Good   (correct with effort)
    4 = Easy   (instant recall)

Reference: https://github.com/open-spaced-repetition/fsrs5
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.models.study import SrsCardState

# ── Constants ─────────────────────────────────────────────────────────────────

DECAY: float = -0.5
# FACTOR is chosen so that R(t=S, S) = 0.9 — i.e. at t=stability days the
# card is at exactly 90% retrievability.
#   (1 + FACTOR)^DECAY = 0.9  →  FACTOR = 0.9^(1/DECAY) − 1 = 19/81
FACTOR: float = 0.9 ** (1 / DECAY) - 1  # ≈ 0.2346

DESIRED_RETENTION: float = 0.9

# ── Default FSRS-5 weights (FSRS-5 paper, Table 1) ───────────────────────────
#
# Index  Meaning
# ─────  ──────────────────────────────────────────────────────────────────────
# 0-3    Initial stability (days) for ratings Again / Hard / Good / Easy
# 4      Initial difficulty base value
# 5      Initial difficulty rating scale
# 6      Difficulty mean-reversion weight toward anchor (Good rating)
# 7      Difficulty change per rating delta from Good
# 8      Recall stability growth base (exponent)
# 9      Recall stability S exponent  (negative — high-S cards grow slower)
# 10     Recall stability R factor
# 11     Forget stability base
# 12     Forget stability D exponent
# 13     Forget stability S exponent
# 14     Forget stability R factor
# 15     Hard penalty multiplier  (applied when rating == Hard in review)
# 16     Easy bonus multiplier    (applied when rating == Easy in review)
# 17     Short-term stability rating scale (learning / relearning states)
# 18     Short-term stability rating offset
DEFAULT_W: list[float] = [
    0.40255, 1.18385,  3.1262,  15.4722,  # 0-3
    7.2102,  0.5316,   1.0651,   0.06408,  # 4-7
    1.46001, 0.14763,  1.11929,  2.21913,  # 8-11
    0.01547, 0.19952,  0.98707,  0.2521,   # 12-15
    2.2604,  0.48,     0.64,               # 16-18
]


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class ScheduleResult:
    """Everything needed to upsert one srs_state row."""
    stability: float
    difficulty: float
    state: SrsCardState
    review_count: int
    last_review: datetime
    due_date: datetime
    # Snapshot written to the srs_data JSONB safety column so that future
    # algorithm changes can be audited or replayed without data loss.
    srs_data: dict = field(default_factory=dict)


# ── Private helpers ───────────────────────────────────────────────────────────

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _forgetting_curve(elapsed_days: float, stability: float) -> float:
    """Retrievability R after *elapsed_days* given *stability* (days)."""
    return (1 + FACTOR * elapsed_days / stability) ** DECAY


def _init_stability(rating: int, w: list[float]) -> float:
    return w[rating - 1]  # w[0]=Again … w[3]=Easy


def _init_difficulty(rating: int, w: list[float]) -> float:
    d = w[4] - math.exp(w[5] * (rating - 1)) + 1
    return _clamp(d, 1.0, 10.0)


def _next_difficulty(d: float, rating: int, w: list[float]) -> float:
    """Mean-reversion update: pulls difficulty toward the Good-rating anchor."""
    anchor = _init_difficulty(3, w)
    d_prime = w[6] * anchor + (1 - w[6]) * (d - w[7] * (rating - 3))
    return _clamp(d_prime, 1.0, 10.0)


def _short_term_stability(s: float, rating: int, w: list[float]) -> float:
    """Stability update for learning/relearning (short-term) states."""
    return s * math.exp(w[17] * (rating - 3 + w[18]))


def _recall_stability(
    d: float, s: float, r: float, rating: int, w: list[float]
) -> float:
    """Stability after a successful recall in review state."""
    hard_penalty = w[15] if rating == 2 else 1.0
    easy_bonus   = w[16] if rating == 4 else 1.0
    return s * (
        math.exp(w[8])
        * (11 - d)
        * s ** (-w[9])
        * (math.exp((1 - r) * w[10]) - 1)
        * hard_penalty
        * easy_bonus
        + 1
    )


def _forget_stability(d: float, s: float, r: float, w: list[float]) -> float:
    """Stability after forgetting (Again rating in review state)."""
    return (
        w[11]
        * d ** (-w[12])
        * ((s + 1) ** w[13] - 1)
        * math.exp((1 - r) * w[14])
    )


def _interval(stability: float) -> int:
    """
    Next review interval in days.

    Because FACTOR is chosen so R(S, S) = DESIRED_RETENTION, the interval at
    which R hits exactly DESIRED_RETENTION equals stability.  We just round.
    Minimum is 1 day.
    """
    return max(1, round(stability))


# ── Public API ────────────────────────────────────────────────────────────────

def schedule(
    *,
    stability: Optional[float],
    difficulty: Optional[float],
    state: SrsCardState,
    review_count: int,
    last_review: Optional[datetime],
    rating: int,
    now: datetime,
    w: list[float] = DEFAULT_W,
) -> ScheduleResult:
    """
    Compute the next SRS state for a card given the user's *rating*.

    Pass stability=None / difficulty=None for a brand-new card
    (state == SrsCardState.new).  All other states require non-None values.

    State transitions
    ─────────────────
    new        + Again/Hard  →  learning  (1-day interval)
    new        + Good/Easy   →  review    (interval = round(S₀))
    learning   + Again/Hard  →  learning  (1-day interval)
    learning   + Good/Easy   →  review    (interval = round(S'))
    review     + Again       →  relearning (1-day interval)
    review     + Hard/Good/Easy → review  (interval = round(S'))
    relearning + Again/Hard  →  relearning (1-day interval)
    relearning + Good/Easy   →  review    (interval = round(S'))
    """
    if rating not in (1, 2, 3, 4):
        raise ValueError(f"rating must be 1–4, got {rating!r}")

    new_review_count = review_count + 1

    # ── New card: first-ever review ───────────────────────────────────────────
    if state == SrsCardState.new:
        new_stability  = _init_stability(rating, w)
        new_difficulty = _init_difficulty(rating, w)

        if rating <= 2:
            new_state, days = SrsCardState.learning, 1
        else:
            new_state, days = SrsCardState.review, _interval(new_stability)

    # ── Short-term states: learning / relearning ──────────────────────────────
    elif state in (SrsCardState.learning, SrsCardState.relearning):
        assert stability is not None and difficulty is not None
        new_difficulty = _next_difficulty(difficulty, rating, w)
        new_stability  = _short_term_stability(stability, rating, w)

        if rating <= 2:
            new_state, days = state, 1          # stay in same short-term state
        else:
            new_state, days = SrsCardState.review, _interval(new_stability)

    # ── Long-term state: review ───────────────────────────────────────────────
    else:
        assert (
            stability is not None
            and difficulty is not None
            and last_review is not None
        )
        elapsed_days   = (now - last_review).total_seconds() / 86_400
        r              = _forgetting_curve(elapsed_days, stability)
        new_difficulty = _next_difficulty(difficulty, rating, w)

        if rating == 1:   # forgot — fall back to relearning
            new_stability = _forget_stability(difficulty, stability, r, w)
            new_state, days = SrsCardState.relearning, 1
        else:             # recalled (Hard / Good / Easy)
            new_stability = _recall_stability(difficulty, stability, r, rating, w)
            new_state, days = SrsCardState.review, _interval(new_stability)

    due_date = now + timedelta(days=days)

    return ScheduleResult(
        stability=new_stability,
        difficulty=new_difficulty,
        state=new_state,
        review_count=new_review_count,
        last_review=now,
        due_date=due_date,
        srs_data={"fsrs_version": 5, "rating": rating, "interval_days": days},
    )
