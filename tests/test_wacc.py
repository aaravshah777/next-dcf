"""Tests for step 2 — the weighted average cost of capital."""

from __future__ import annotations

import pytest

from dcf.inputs import EquityBridge, MarketData, WaccInputs
from dcf.wacc import compute_wacc, cost_of_equity, relever_beta, unlever_beta

BRIDGE = EquityBridge(shares_outstanding=119.66, minority_interests=118.0)
MARKET = MarketData(share_price_pence=14210.0)
NET_DEBT = 2744.0

INPUTS = WaccInputs(
    risk_free_rate=0.0548,
    equity_risk_premium=0.0500,
    country_risk_premium=0.0,
    levered_beta=1.05,
    pre_tax_cost_of_debt=0.0630,
    marginal_tax_rate=0.25,
)


def test_capm_cost_of_equity():
    # 5.48% + 1.05 * 5.00% = 10.73%
    assert cost_of_equity(0.0548, 1.05, 0.05) == pytest.approx(0.1073, abs=1e-9)


def test_beta_of_one_returns_market_return():
    assert cost_of_equity(0.0548, 1.0, 0.05) == pytest.approx(0.1048)


def test_beta_above_one_raises_cost_of_equity_above_the_market():
    """A cyclical retailer should demand more than the market return."""
    market_return = cost_of_equity(0.0548, 1.0, 0.05)
    assert cost_of_equity(0.0548, 1.05, 0.05) > market_return


def test_country_risk_premium_is_additive():
    base = cost_of_equity(0.0548, 1.05, 0.05)
    assert cost_of_equity(0.0548, 1.05, 0.05, 0.01) == pytest.approx(base + 0.01)


def test_unlever_then_relever_is_identity():
    original = 1.05
    unlevered = unlever_beta(original, 0.161, 0.25)
    assert relever_beta(unlevered, 0.161, 0.25) == pytest.approx(original)


def test_unlevered_beta_is_lower_than_levered():
    assert unlever_beta(1.05, 0.161, 0.25) < 1.05


def test_tax_shield_reduces_cost_of_debt():
    result = compute_wacc(INPUTS, BRIDGE, MARKET, NET_DEBT)
    assert result.after_tax_cost_of_debt == pytest.approx(0.063 * 0.75)
    assert result.after_tax_cost_of_debt < result.pre_tax_cost_of_debt


def test_market_value_of_equity_uses_price_times_shares():
    result = compute_wacc(INPUTS, BRIDGE, MARKET, NET_DEBT)
    assert result.market_value_equity == pytest.approx(142.10 * 119.66)


def test_weights_sum_to_one():
    result = compute_wacc(INPUTS, BRIDGE, MARKET, NET_DEBT)
    assert result.weight_equity + result.weight_debt == pytest.approx(1.0)


def test_wacc_sits_between_cost_of_debt_and_cost_of_equity():
    result = compute_wacc(INPUTS, BRIDGE, MARKET, NET_DEBT)
    assert result.after_tax_cost_of_debt < result.wacc < result.cost_of_equity


def test_including_leases_in_debt_changes_the_weights():
    """Lease liabilities are real debt under IFRS 16, so they shift the mix."""
    without_leases = compute_wacc(INPUTS, BRIDGE, MARKET, 1714.0)
    with_leases = compute_wacc(INPUTS, BRIDGE, MARKET, 2744.0)
    assert with_leases.weight_debt > without_leases.weight_debt
    assert with_leases.wacc < without_leases.wacc  # more cheap debt in the mix


def test_higher_gilt_yield_raises_the_wacc():
    """The current gilt level is the single biggest driver of Next's WACC."""
    import dataclasses

    low_gilt = dataclasses.replace(INPUTS, risk_free_rate=0.040)
    assert (
        compute_wacc(low_gilt, BRIDGE, MARKET, NET_DEBT).wacc
        < compute_wacc(INPUTS, BRIDGE, MARKET, NET_DEBT).wacc
    )


def test_share_price_converts_pence_to_pounds():
    assert MARKET.share_price_pounds == pytest.approx(142.10)


def test_invalid_debt_measure_is_rejected():
    with pytest.raises(ValueError, match="debt_measure"):
        WaccInputs(
            risk_free_rate=0.0548,
            equity_risk_premium=0.05,
            country_risk_premium=0.0,
            levered_beta=1.05,
            pre_tax_cost_of_debt=0.063,
            marginal_tax_rate=0.25,
            debt_measure="book_debt",
        )
