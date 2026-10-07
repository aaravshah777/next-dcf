"""Tests for steps 4 and 5 — discounting and the equity bridge."""

from __future__ import annotations

import pytest

from dcf.forecast import forecast_free_cash_flow
from dcf.inputs import BaseYearFinancials, EquityBridge, ForecastDrivers, MarketData
from dcf.terminal import compute_terminal_value
from dcf.valuation import discount_cash_flows, discount_factor, value_equity

BRIDGE = EquityBridge(
    shares_outstanding=119.66, minority_interests=118.0, investments=35.2
)
MARKET = MarketData(share_price_pence=14210.0)


@pytest.fixture
def forecast():
    base = BaseYearFinancials(
        revenue=6901.0,
        operating_profit=1276.0,
        profit_before_tax=1190.0,
        depreciation_amortisation=325.3,
        capital_expenditure=135.4,
        reported_free_cash_flow=1098.0,
        net_debt_excluding_leases=1714.0,
        lease_liabilities=1030.0,
        customer_receivables=1583.0,
    )
    drivers = ForecastDrivers(
        years=["FY2027", "FY2028", "FY2029"],
        revenue_growth=[0.04, 0.045, 0.04],
        operating_margin=[0.186, 0.187, 0.188],
        depreciation_amortisation_pct_revenue=[0.047, 0.047, 0.0465],
        rou_depreciation_pct_revenue=[0.025, 0.025, 0.025],
        cash_rent_pct_revenue=[0.030, 0.030, 0.0295],
        capex_pct_revenue=[0.020, 0.020, 0.020],
        net_working_capital_pct_revenue=[0.20, 0.20, 0.198],
        effective_tax_rate=0.255,
    )
    return forecast_free_cash_flow(base, drivers)


def _terminal(forecast, wacc=0.099):
    return compute_terminal_value(
        forecast.terminal_year_fcf,
        forecast.terminal_year_ebitda,
        wacc,
        perpetuity_growth_rate=0.025,
    )


def test_discount_factor_matches_the_formula():
    assert discount_factor(0.099, 3) == pytest.approx(1 / 1.099**3)


def test_discount_factor_of_zero_period_is_one():
    assert discount_factor(0.099, 0) == pytest.approx(1.0)


def test_discount_factors_decline_with_time():
    factors = [discount_factor(0.099, t) for t in range(1, 6)]
    assert all(a > b for a, b in zip(factors, factors[1:]))


def test_year_end_periods_are_whole_numbers(forecast):
    table = discount_cash_flows(forecast, 0.099, mid_year_convention=False)
    assert list(table["discount_period"]) == [1.0, 2.0, 3.0]


def test_mid_year_periods_are_offset_by_half(forecast):
    table = discount_cash_flows(forecast, 0.099, mid_year_convention=True)
    assert list(table["discount_period"]) == [0.5, 1.5, 2.5]


def test_mid_year_uplift_is_root_one_plus_wacc(forecast):
    year_end = discount_cash_flows(forecast, 0.099, mid_year_convention=False)
    mid_year = discount_cash_flows(forecast, 0.099, mid_year_convention=True)
    ratio = mid_year["pv_free_cash_flow"].sum() / year_end["pv_free_cash_flow"].sum()
    assert ratio == pytest.approx(1.099**0.5, rel=1e-9)


def test_enterprise_value_is_the_sum_of_its_parts(forecast):
    result = value_equity(forecast, _terminal(forecast), 0.099, BRIDGE, MARKET, 2744.0)
    assert result.enterprise_value == pytest.approx(
        result.pv_explicit_fcf + result.pv_terminal_value
    )


def test_equity_bridge_subtracts_claims_and_adds_investments(forecast):
    result = value_equity(forecast, _terminal(forecast), 0.099, BRIDGE, MARKET, 2744.0)
    assert result.equity_value == pytest.approx(
        result.enterprise_value - 2744.0 - 118.0 + 35.2
    )


def test_equity_value_is_below_enterprise_value(forecast):
    """Next carries net debt, so equity must be worth less than EV."""
    result = value_equity(forecast, _terminal(forecast), 0.099, BRIDGE, MARKET, 2744.0)
    assert result.equity_value < result.enterprise_value


def test_terminal_value_is_discounted_over_the_full_horizon(forecast):
    """Three forecast years means the TV is discounted at t=3, even with mid-year."""
    terminal = _terminal(forecast)
    result = value_equity(
        forecast, terminal, 0.099, BRIDGE, MARKET, 0.0, mid_year_convention=True
    )
    assert result.pv_terminal_value == pytest.approx(
        terminal.terminal_value * discount_factor(0.099, 3.0)
    )


def test_price_converts_pounds_to_pence(forecast):
    result = value_equity(forecast, _terminal(forecast), 0.099, BRIDGE, MARKET, 2744.0)
    assert result.implied_share_price_pence == pytest.approx(
        result.implied_share_price_pounds * 100.0
    )


def test_upside_is_measured_against_the_market_price(forecast):
    result = value_equity(forecast, _terminal(forecast), 0.099, BRIDGE, MARKET, 2744.0)
    assert result.upside_downside == pytest.approx(
        result.implied_share_price_pence / 14210.0 - 1.0
    )


def test_more_debt_deducted_lowers_the_implied_price(forecast):
    """This is why the lease treatment matters so much."""
    low = value_equity(forecast, _terminal(forecast), 0.099, BRIDGE, MARKET, 1714.0)
    high = value_equity(forecast, _terminal(forecast), 0.099, BRIDGE, MARKET, 2744.0)
    assert high.implied_share_price_pence < low.implied_share_price_pence


def test_higher_wacc_produces_a_lower_price(forecast):
    prices = []
    for wacc in (0.090, 0.110):
        prices.append(
            value_equity(
                forecast, _terminal(forecast, wacc), wacc, BRIDGE, MARKET, 2744.0
            ).implied_share_price_pence
        )
    assert prices[1] < prices[0]


def test_zero_shares_outstanding_is_rejected():
    with pytest.raises(ValueError, match="shares_outstanding"):
        EquityBridge(shares_outstanding=0.0)
