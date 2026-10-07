"""Tests for step 1 — the free cash flow forecast."""

from __future__ import annotations

import pytest

from dcf.forecast import forecast_free_cash_flow
from dcf.inputs import BaseYearFinancials, ForecastDrivers


@pytest.fixture
def base() -> BaseYearFinancials:
    return BaseYearFinancials(
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


@pytest.fixture
def drivers() -> ForecastDrivers:
    return ForecastDrivers(
        years=["FY2027", "FY2028"],
        revenue_growth=[0.04, 0.045],
        operating_margin=[0.186, 0.187],
        depreciation_amortisation_pct_revenue=[0.047, 0.047],
        rou_depreciation_pct_revenue=[0.025, 0.025],
        cash_rent_pct_revenue=[0.030, 0.030],
        capex_pct_revenue=[0.020, 0.020],
        net_working_capital_pct_revenue=[0.20, 0.20],
        effective_tax_rate=0.255,
    )


def test_base_year_margin_matches_reported(base):
    assert base.operating_margin == pytest.approx(0.1849, abs=1e-4)


def test_capex_is_well_below_depreciation(base):
    """A lease-heavy retailer spends far less on capex than it depreciates."""
    assert base.capex_to_depreciation < 0.5


def test_credit_book_is_a_large_share_of_revenue(base):
    """Next Finance receivables are c.23% of revenue, which drives working capital."""
    assert base.credit_book_pct_revenue > 0.20


def test_net_debt_including_leases_adds_the_two_components(base):
    assert base.net_debt_including_leases == pytest.approx(1714.0 + 1030.0)


def test_revenue_compounds_at_the_growth_rate(base, drivers):
    table = forecast_free_cash_flow(base, drivers).table
    assert table.loc[0, "revenue"] == pytest.approx(6901.0 * 1.04)
    assert table.loc[1, "revenue"] == pytest.approx(6901.0 * 1.04 * 1.045)


def test_fcf_build_reconciles_line_by_line(base, drivers):
    """Rebuild year one by hand and check every line against it (IFRS 16 basis)."""
    table = forecast_free_cash_flow(base, drivers, lease_treatment="capitalised").table
    row = table.loc[0]

    revenue = 6901.0 * 1.04
    ebit = revenue * 0.186
    nopat = ebit * 0.745
    d_and_a = revenue * 0.047
    capex = revenue * 0.020
    change_in_nwc = (revenue * 0.20) - (6901.0 * 0.20)
    expected_fcf = nopat + d_and_a - capex - change_in_nwc

    assert row["revenue"] == pytest.approx(revenue)
    assert row["ebit"] == pytest.approx(ebit)
    assert row["nopat"] == pytest.approx(nopat)
    assert row["free_cash_flow"] == pytest.approx(expected_fcf)


def test_ebitda_equals_ebit_plus_total_depreciation(base, drivers):
    table = forecast_free_cash_flow(base, drivers).table
    assert (
        table["ebitda"] - (table["ebit"] + table["depreciation_amortisation"])
    ).abs().max() < 1e-9


def test_positive_working_capital_consumes_cash_as_revenue_grows(base, drivers):
    """The credit book means growth ties up cash — the opposite of a grocer."""
    table = forecast_free_cash_flow(base, drivers).table
    assert (table["change_in_net_working_capital"] > 0).all()


def test_growth_delta_shifts_every_year(base, drivers):
    baseline = forecast_free_cash_flow(base, drivers).table
    shifted = forecast_free_cash_flow(base, drivers, growth_delta=0.01).table
    assert (shifted["revenue"] > baseline["revenue"]).all()


def test_margin_delta_raises_free_cash_flow(base, drivers):
    baseline = forecast_free_cash_flow(base, drivers)
    shifted = forecast_free_cash_flow(base, drivers, margin_delta=0.01)
    assert shifted.terminal_year_fcf > baseline.terminal_year_fcf


def test_mismatched_driver_lengths_are_rejected():
    with pytest.raises(ValueError, match="one value per year"):
        ForecastDrivers(
            years=["FY2027", "FY2028", "FY2029"],
            revenue_growth=[0.04, 0.04],  # one short
            operating_margin=[0.186, 0.187, 0.188],
            depreciation_amortisation_pct_revenue=[0.047, 0.047, 0.047],
            rou_depreciation_pct_revenue=[0.025, 0.025, 0.025],
            cash_rent_pct_revenue=[0.030, 0.030, 0.030],
            capex_pct_revenue=[0.020, 0.020, 0.020],
            net_working_capital_pct_revenue=[0.20, 0.20, 0.20],
            effective_tax_rate=0.255,
        )


def test_impossible_tax_rate_is_rejected():
    with pytest.raises(ValueError, match="effective_tax_rate"):
        ForecastDrivers(
            years=["FY2027"],
            revenue_growth=[0.04],
            operating_margin=[0.186],
            depreciation_amortisation_pct_revenue=[0.047],
            rou_depreciation_pct_revenue=[0.025],
            cash_rent_pct_revenue=[0.030],
            capex_pct_revenue=[0.020],
            net_working_capital_pct_revenue=[0.20],
            effective_tax_rate=1.4,
        )
