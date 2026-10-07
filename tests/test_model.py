"""End-to-end tests: load the real assumptions file and run the whole model."""

from __future__ import annotations

from pathlib import Path

import pytest

from dcf import load_assumptions, run_dcf, wacc_vs_growth, wacc_vs_margin

ASSUMPTIONS = Path(__file__).resolve().parents[1] / "assumptions.yaml"


@pytest.fixture(scope="module")
def assumptions():
    return load_assumptions(ASSUMPTIONS)


@pytest.fixture(scope="module")
def output(assumptions):
    return run_dcf(assumptions)


def test_assumptions_file_loads(assumptions):
    assert assumptions.base.revenue == 6901.0
    assert assumptions.forecast.horizon == 5


def test_model_runs_end_to_end(output):
    assert output.valuation.implied_share_price_pence > 0
    assert output.valuation.enterprise_value > 0


def test_wacc_is_plausible_for_a_uk_retailer(output):
    """A cyclical retailer with gilts near 5.5% should land in a high band."""
    assert 0.07 < output.wacc.wacc < 0.14


def test_cost_of_equity_exceeds_the_gilt_yield(output, assumptions):
    """Equity must be compensated above the risk-free rate."""
    assert output.wacc.cost_of_equity > assumptions.wacc.risk_free_rate


def test_terminal_value_dominates_but_not_absurdly(output):
    assert 0.55 < output.valuation.terminal_value_share_of_ev < 0.90


def test_forecast_free_cash_flow_grows_over_the_horizon(output):
    flows = output.forecast.free_cash_flow
    assert all(b > a for a, b in zip(flows, flows[1:]))


def test_first_year_fcf_is_in_a_sane_range_versus_reported(output):
    """FY2026 reported FCF was £1,098m, after interest and cash tax.

    Our unlevered figure should sit in the same region: above the levered
    number but not a multiple of it, otherwise the operating assumptions have
    drifted away from the actual accounts.
    """
    first_year = output.forecast.free_cash_flow[0]
    assert 900.0 < first_year < 1.6 * 1098.0


def test_raising_the_discount_rate_lowers_the_price(assumptions):
    base = run_dcf(assumptions).valuation.implied_share_price_pence
    higher = run_dcf(assumptions, wacc_delta=0.01).valuation.implied_share_price_pence
    assert higher < base


def test_raising_terminal_growth_raises_the_price(assumptions):
    base = run_dcf(assumptions).valuation.implied_share_price_pence
    higher = run_dcf(
        assumptions, terminal_growth_delta=0.005
    ).valuation.implied_share_price_pence
    assert higher > base


def test_sensitivity_grids_have_the_expected_shape(assumptions):
    grid = wacc_vs_growth(assumptions)
    assert grid.shape == (
        len(assumptions.sensitivity.wacc_deltas),
        len(assumptions.sensitivity.growth_deltas),
    )


def test_sensitivity_prices_fall_as_wacc_rises(assumptions):
    grid = wacc_vs_growth(assumptions)
    for column in grid.columns:
        values = grid[column].dropna().tolist()
        assert all(a > b for a, b in zip(values, values[1:]))


def test_margin_grid_prices_rise_across_the_columns(assumptions):
    grid = wacc_vs_margin(assumptions)
    for _, row in grid.iterrows():
        values = row.dropna().tolist()
        assert all(a < b for a, b in zip(values, values[1:]))


def test_grid_still_produces_real_values(assumptions):
    """Impossible corners return NaN rather than killing the whole grid."""
    grid = wacc_vs_growth(assumptions)
    assert grid.notna().to_numpy().sum() > 0
