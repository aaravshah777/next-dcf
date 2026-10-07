"""Tests for step 3 — terminal value."""

from __future__ import annotations

import pytest

from dcf.terminal import (
    compute_terminal_value,
    exit_multiple_terminal_value,
    gordon_growth_terminal_value,
    implied_exit_multiple,
    implied_perpetuity_growth,
)


def test_gordon_growth_matches_the_formula():
    # 1000 * 1.025 / (0.099 - 0.025) = 13,851.35...
    assert gordon_growth_terminal_value(1000.0, 0.099, 0.025) == pytest.approx(
        1000 * 1.025 / 0.074
    )


def test_gordon_growth_includes_the_one_plus_g_step():
    """The numerator must grow one more year; omitting it understates TV."""
    with_growth = gordon_growth_terminal_value(1000.0, 0.099, 0.025)
    without_growth = 1000.0 / (0.099 - 0.025)
    assert with_growth == pytest.approx(without_growth * 1.025)


def test_zero_growth_is_a_simple_perpetuity():
    assert gordon_growth_terminal_value(1000.0, 0.10, 0.0) == pytest.approx(10000.0)


def test_growth_above_wacc_raises():
    with pytest.raises(ValueError, match="must be below the WACC"):
        gordon_growth_terminal_value(1000.0, 0.05, 0.06)


def test_growth_equal_to_wacc_raises():
    with pytest.raises(ValueError):
        gordon_growth_terminal_value(1000.0, 0.05, 0.05)


def test_higher_growth_raises_terminal_value():
    low = gordon_growth_terminal_value(1000.0, 0.099, 0.015)
    high = gordon_growth_terminal_value(1000.0, 0.099, 0.030)
    assert high > low


def test_higher_wacc_lowers_terminal_value():
    assert gordon_growth_terminal_value(
        1000.0, 0.11, 0.025
    ) < gordon_growth_terminal_value(1000.0, 0.09, 0.025)


def test_exit_multiple_is_ebitda_times_multiple():
    assert exit_multiple_terminal_value(1954.0, 8.0) == pytest.approx(15632.0)


def test_negative_exit_multiple_raises():
    with pytest.raises(ValueError, match="positive"):
        exit_multiple_terminal_value(1954.0, -1.0)


def test_implied_exit_multiple_inverts_cleanly():
    assert implied_exit_multiple(15632.0, 1954.0) == pytest.approx(8.0)


def test_implied_growth_round_trips_with_gordon_growth():
    tv = gordon_growth_terminal_value(1000.0, 0.099, 0.025)
    assert implied_perpetuity_growth(tv, 1000.0, 0.099) == pytest.approx(0.025)


def test_compute_terminal_value_reports_both_methods():
    result = compute_terminal_value(
        final_year_fcf=1352.0,
        final_year_ebitda=1954.0,
        wacc=0.099,
        method="gordon_growth",
        perpetuity_growth_rate=0.025,
        exit_ev_ebitda_multiple=8.0,
    )
    assert result.terminal_value == result.gordon_growth_value
    assert result.exit_multiple_value == pytest.approx(15632.0)
    assert result.implied_exit_ev_ebitda > 0


def test_retail_exit_multiple_is_lower_than_a_staple():
    """Sanity check on the assumption: 8x retail vs 12x for consumer staples."""
    retail = exit_multiple_terminal_value(1954.0, 8.0)
    staple = exit_multiple_terminal_value(1954.0, 12.0)
    assert retail < staple


def test_switching_method_changes_the_chosen_value():
    kwargs = dict(
        final_year_fcf=1352.0,
        final_year_ebitda=1954.0,
        wacc=0.099,
        perpetuity_growth_rate=0.025,
        exit_ev_ebitda_multiple=8.0,
    )
    gordon = compute_terminal_value(method="gordon_growth", **kwargs)
    exit_based = compute_terminal_value(method="exit_multiple", **kwargs)
    assert gordon.terminal_value != exit_based.terminal_value
    assert exit_based.terminal_value == pytest.approx(15632.0)
