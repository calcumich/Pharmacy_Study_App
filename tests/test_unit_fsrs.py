"""
Unit tests for the FSRS-5 scheduling algorithm (app/services/fsrs.py).

No DB, no HTTP — these tests exercise the pure scheduling math.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.study import SrsCardState
from app.services.fsrs import (
    DEFAULT_W,
    ScheduleResult,
    _forgetting_curve,
    _init_difficulty,
    _init_stability,
    _interval,
    schedule,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _new_card_state() -> dict:
    return dict(
        stability=None,
        difficulty=None,
        state=SrsCardState.new,
        review_count=0,
        last_review=None,
    )


def _reviewed_state(
    *,
    stability: float,
    difficulty: float,
    state: SrsCardState = SrsCardState.review,
    review_count: int = 1,
    last_review: datetime = NOW,
) -> dict:
    return dict(
        stability=stability,
        difficulty=difficulty,
        state=state,
        review_count=review_count,
        last_review=last_review,
    )


# ── forgetting_curve ──────────────────────────────────────────────────────────

def test_retrievability_at_stability_is_90_percent():
    """R(t=S, S) must equal DESIRED_RETENTION (0.9) — the FACTOR definition."""
    for s in (1.0, 5.0, 20.0):
        r = _forgetting_curve(elapsed_days=s, stability=s)
        assert abs(r - 0.9) < 1e-9


def test_retrievability_decreases_over_time():
    s = 10.0
    r_early = _forgetting_curve(5.0, s)
    r_late  = _forgetting_curve(15.0, s)
    assert r_early > 0.9 > r_late


# ── _interval ─────────────────────────────────────────────────────────────────

def test_interval_minimum_is_one():
    assert _interval(0.0) == 1
    assert _interval(0.4) == 1


def test_interval_rounds_stability():
    assert _interval(3.1) == 3
    assert _interval(3.5) == 4


# ── New card (first review) ───────────────────────────────────────────────────

@pytest.mark.parametrize("rating", [1, 2, 3, 4])
def test_new_card_increments_review_count(rating: int):
    result = schedule(**_new_card_state(), rating=rating, now=NOW)
    assert result.review_count == 1


@pytest.mark.parametrize("rating, expected_state", [
    (1, SrsCardState.learning),
    (2, SrsCardState.learning),
    (3, SrsCardState.review),
    (4, SrsCardState.review),
])
def test_new_card_state_transitions(rating: int, expected_state: SrsCardState):
    result = schedule(**_new_card_state(), rating=rating, now=NOW)
    assert result.state == expected_state


@pytest.mark.parametrize("rating", [1, 2])
def test_new_card_again_hard_gives_one_day_interval(rating: int):
    result = schedule(**_new_card_state(), rating=rating, now=NOW)
    assert result.due_date == NOW + timedelta(days=1)


@pytest.mark.parametrize("rating", [3, 4])
def test_new_card_good_easy_gives_multi_day_interval(rating: int):
    result = schedule(**_new_card_state(), rating=rating, now=NOW)
    assert result.due_date > NOW + timedelta(days=1)


def test_new_card_easy_longer_than_good():
    good = schedule(**_new_card_state(), rating=3, now=NOW)
    easy = schedule(**_new_card_state(), rating=4, now=NOW)
    assert easy.due_date > good.due_date


def test_new_card_stability_matches_w_index():
    for rating in (1, 2, 3, 4):
        result = schedule(**_new_card_state(), rating=rating, now=NOW)
        assert result.stability == pytest.approx(DEFAULT_W[rating - 1])


def test_new_card_difficulty_in_range():
    for rating in (1, 2, 3, 4):
        result = schedule(**_new_card_state(), rating=rating, now=NOW)
        assert 1.0 <= result.difficulty <= 10.0


# ── Learning state ────────────────────────────────────────────────────────────

def test_learning_again_stays_learning():
    state = _reviewed_state(stability=1.0, difficulty=5.0, state=SrsCardState.learning)
    result = schedule(**state, rating=1, now=NOW)
    assert result.state == SrsCardState.learning
    assert result.due_date == NOW + timedelta(days=1)


def test_learning_good_graduates_to_review():
    state = _reviewed_state(stability=3.0, difficulty=5.0, state=SrsCardState.learning)
    result = schedule(**state, rating=3, now=NOW)
    assert result.state == SrsCardState.review
    assert result.due_date > NOW + timedelta(days=1)


# ── Review state ──────────────────────────────────────────────────────────────

def test_review_again_drops_to_relearning():
    state = _reviewed_state(stability=10.0, difficulty=5.0)
    result = schedule(**state, rating=1, now=NOW + timedelta(days=10))
    assert result.state == SrsCardState.relearning
    assert result.due_date == NOW + timedelta(days=10 + 1)


def test_review_good_stays_review_with_longer_interval():
    state = _reviewed_state(stability=10.0, difficulty=5.0)
    result = schedule(**state, rating=3, now=NOW + timedelta(days=10))
    assert result.state == SrsCardState.review
    assert result.stability > 10.0  # stability grows after successful recall
    assert result.due_date > NOW + timedelta(days=10 + 10)  # longer than before


def test_review_easy_longer_than_good():
    state = _reviewed_state(stability=10.0, difficulty=5.0)
    kwargs = dict(now=NOW + timedelta(days=10))
    good = schedule(**state, rating=3, **kwargs)
    easy = schedule(**state, rating=4, **kwargs)
    assert easy.stability > good.stability
    assert easy.due_date > good.due_date


def test_review_hard_shorter_than_good():
    state = _reviewed_state(stability=10.0, difficulty=5.0)
    kwargs = dict(now=NOW + timedelta(days=10))
    hard = schedule(**state, rating=2, **kwargs)
    good = schedule(**state, rating=3, **kwargs)
    assert hard.stability < good.stability


def test_review_count_accumulates():
    state = _new_card_state()
    r1 = schedule(**state, rating=3, now=NOW)
    assert r1.review_count == 1
    r2 = schedule(**_reviewed_state(
        stability=r1.stability, difficulty=r1.difficulty,
        state=r1.state, review_count=r1.review_count, last_review=NOW,
    ), rating=3, now=NOW + timedelta(days=3))
    assert r2.review_count == 2


# ── Relearning state ──────────────────────────────────────────────────────────

def test_relearning_good_graduates_to_review():
    state = _reviewed_state(stability=2.0, difficulty=6.0, state=SrsCardState.relearning)
    result = schedule(**state, rating=3, now=NOW)
    assert result.state == SrsCardState.review


def test_relearning_again_stays_relearning():
    state = _reviewed_state(stability=2.0, difficulty=6.0, state=SrsCardState.relearning)
    result = schedule(**state, rating=1, now=NOW)
    assert result.state == SrsCardState.relearning
    assert result.due_date == NOW + timedelta(days=1)


# ── srs_data snapshot ─────────────────────────────────────────────────────────

def test_srs_data_contains_fsrs_version_and_rating():
    result = schedule(**_new_card_state(), rating=3, now=NOW)
    assert result.srs_data["fsrs_version"] == 5
    assert result.srs_data["rating"] == 3
    assert "interval_days" in result.srs_data


# ── Invalid rating ────────────────────────────────────────────────────────────

def test_invalid_rating_raises():
    with pytest.raises(ValueError, match="rating"):
        schedule(**_new_card_state(), rating=0, now=NOW)

    with pytest.raises(ValueError, match="rating"):
        schedule(**_new_card_state(), rating=5, now=NOW)
