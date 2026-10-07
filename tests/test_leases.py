"""Tests for the IFRS 16 lease treatment — the part most specific to a retailer.

The rule these tests enforce: whether right-of-use depreciation is added back
and whether lease liabilities are deducted as debt must ALWAYS move together.
Taking the add-back without the liability is the error that inflates a
lease-heavy retailer's equity value by over £1bn.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from dcf import load_assumptions, run_dcf
from dcf.forecast import forecast_free_cash_flow
from dcf.sensitivity import lease_treatment_comparison

ASSUMPTIONS = Path(__file__).resolve().parents[1] / "assumptions.yaml"


@pytest.fixture(scope="module")
def assumptions():
    return load_assumptions(ASSUMPTIONS)


def test_capitalised_adds_back_all_depreciation(assumptions):
    result = forecast_free_cash_flow(
        assumptions.base, assumptions.forecast, lease_treatment="capitalised"
    )
    row = result.table.iloc[0]
    assert row["d_and_a_added_back"] == pytest.approx(row["depreciation_amortisation"])


def test_expensed_excludes_lease_depreciation_from_the_add_back(assumptions):
    result = forecast_free_cash_flow(
        assumptions.base, assumptions.forecast, lease_treatment="expensed"
    )
    row = result.table.iloc[0]
    expected = row["depreciation_amortisation"] - row["rou_depreciation"]
    assert row["d_and_a_added_back"] == pytest.approx(expected)


def test_expensed_charges_full_cash_rent_against_ebit(assumptions):
    """Pre-IFRS 16 EBIT = IFRS 16 EBIT + ROU depreciation - cash rent."""
    capitalised = forecast_free_cash_flow(
        assumptions.base, assumptions.forecast, lease_treatment="capitalised"
    ).table.iloc[0]
    expensed = forecast_free_cash_flow(
        assumptions.base, assumptions.forecast, lease_treatment="expensed"
    ).table.iloc[0]

    expected = (
        capitalised["ebit"] + capitalised["rou_depreciation"] - capitalised["cash_rent"]
    )
    assert expensed["ebit"] == pytest.approx(expected)


def test_expensed_ebit_is_lower_because_rent_exceeds_lease_depreciation(assumptions):
    """Cash rent includes the lease interest, which IFRS 16 reports below EBIT."""
    capitalised = forecast_free_cash_flow(
        assumptions.base, assumptions.forecast, lease_treatment="capitalised"
    ).table.iloc[0]
    expensed = forecast_free_cash_flow(
        assumptions.base, assumptions.forecast, lease_treatment="expensed"
    ).table.iloc[0]
    assert expensed["ebit"] < capitalised["ebit"]


def test_capitalised_deducts_lease_liabilities_as_debt(assumptions):
    output = run_dcf(assumptions)
    assert output.valuation.net_debt_deducted == pytest.approx(
        assumptions.base.net_debt_excluding_leases + assumptions.base.lease_liabilities
    )


def test_expensed_does_not_deduct_lease_liabilities(assumptions):
    variant = dataclasses.replace(assumptions, lease_treatment="expensed")
    output = run_dcf(variant)
    assert output.valuation.net_debt_deducted == pytest.approx(
        assumptions.base.net_debt_excluding_leases
    )


def test_leases_are_debt_flag_follows_the_treatment(assumptions):
    assert assumptions.leases_are_debt is True
    expensed = dataclasses.replace(assumptions, lease_treatment="expensed")
    assert expensed.leases_are_debt is False


def test_lease_comparison_returns_both_treatments(assumptions):
    table = lease_treatment_comparison(assumptions)
    assert set(table.index) == {"capitalised", "expensed"}
    assert (table["equity value"] > 0).all()


def test_invalid_lease_treatment_is_rejected(tmp_path):
    bad = ASSUMPTIONS.read_text(encoding="utf-8").replace(
        "lease_treatment: capitalised", "lease_treatment: ignored"
    )
    path = tmp_path / "bad.yaml"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError, match="lease_treatment"):
        load_assumptions(path)


def test_lease_depreciation_cannot_exceed_total_depreciation(assumptions):
    """A sanity check on the inputs: ROU depreciation is part of D&A.

    Validation runs in __post_init__, so the replace call itself raises.
    """
    with pytest.raises(ValueError, match="exceeds total D&A"):
        dataclasses.replace(
            assumptions.forecast,
            rou_depreciation_pct_revenue=[0.99] * assumptions.forecast.horizon,
        )


def test_cash_rent_below_lease_depreciation_is_rejected(assumptions):
    with pytest.raises(ValueError, match="below right-of-use depreciation"):
        dataclasses.replace(
            assumptions.forecast,
            cash_rent_pct_revenue=[0.001] * assumptions.forecast.horizon,
        )
