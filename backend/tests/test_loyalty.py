from datetime import time
from decimal import Decimal
from types import SimpleNamespace

from app.services.loyalty import _safe_multiplier, _time_in_window, calculate_deltas


def program(**overrides):
    data = dict(
        enabled=True,
        program_type="hybrid",
        points_per_visit=10,
        points_per_currency=2,
        cashback_percent=5,
        birthday_bonus=50,
        referral_bonus=25,
        allow_manual_adjustment=True,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_visit_hybrid():
    assert calculate_deltas(program(), "visit", Decimal("0"), 0, 0) == (10, 1)


def test_spend_points():
    assert calculate_deltas(program(), "spend", Decimal("12.5"), 0, 0) == (25, 0)


def test_cashback():
    assert calculate_deltas(program(program_type="cashback"), "spend", Decimal("200"), 0, 0) == (10, 0)


def test_manual():
    assert calculate_deltas(program(), "manual", Decimal("0"), -5, 2) == (-5, 2)


def test_disabled():
    assert calculate_deltas(program(enabled=False), "visit", Decimal("0"), 0, 0) == (0, 0)


def test_safe_multiplier_valid_invalid_and_cap():
    assert _safe_multiplier("2.5") == Decimal("2.5")
    assert _safe_multiplier("not-a-number") == Decimal("1")
    assert _safe_multiplier(0) == Decimal("1")
    assert _safe_multiplier(999) == Decimal("20")


def test_time_window_normal():
    assert _time_in_window(time(15, 0), "14:00", "17:00") is True
    assert _time_in_window(time(18, 0), "14:00", "17:00") is False


def test_time_window_overnight():
    assert _time_in_window(time(23, 30), "22:00", "02:00") is True
    assert _time_in_window(time(1, 30), "22:00", "02:00") is True
    assert _time_in_window(time(12, 0), "22:00", "02:00") is False


def test_time_window_invalid_input():
    assert _time_in_window(time(12, 0), "bad", "17:00") is False
