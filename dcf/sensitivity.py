"""Sensitivity analysis.

A DCF produces a single number with about six significant figures and roughly
one of them is meaningful. The honest output is a RANGE, and the honest
question is "which assumption is this valuation actually betting on?"

Three tables are produced:

* WACC vs terminal growth — the classic. Both sit in the denominator of the
  terminal value, so the valuation is more sensitive to them than to anything
  in the explicit forecast. For Next this matters especially: the gilt yield is
  near a 2008 high, so the base-case WACC is unusually high and unusually
  likely to move.
* WACC vs operating margin — tests the operating case rather than the
  discount-rate machinery.
* Lease treatment — compares the IFRS 16 and pre-IFRS 16 views of the same
  business. Done consistently they should land reasonably close together; a
  large gap means one of the lease inputs needs checking.

Cells that break the model (terminal growth at or above the WACC) come back as
NaN rather than throwing, so one impossible corner does not kill the grid.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from .inputs import Assumptions
from .model import run_dcf

__all__ = ["wacc_vs_growth", "wacc_vs_margin", "lease_treatment_comparison",
           "summary_statistics"]


def _safe_price(assumptions: Assumptions, **deltas: float) -> float:
    """Run the model and return the implied price, or NaN if the case is invalid."""
    try:
        return run_dcf(assumptions, **deltas).valuation.implied_share_price_pence
    except ValueError:
        # Raised when terminal growth >= WACC. That corner has no finite answer.
        return float("nan")


def wacc_vs_growth(assumptions: Assumptions) -> pd.DataFrame:
    """Implied share price (pence) across WACC and terminal growth shifts."""
    grid = assumptions.sensitivity
    base_wacc = run_dcf(assumptions).wacc.wacc
    base_growth = assumptions.terminal_value.perpetuity_growth_rate

    data = {}
    for g_delta in grid.growth_deltas:
        column = f"g = {base_growth + g_delta:.2%}"
        data[column] = [
            _safe_price(assumptions, wacc_delta=w_delta, terminal_growth_delta=g_delta)
            for w_delta in grid.wacc_deltas
        ]

    index = [f"WACC = {base_wacc + w:.2%}" for w in grid.wacc_deltas]
    return pd.DataFrame(data, index=index)


def wacc_vs_margin(assumptions: Assumptions) -> pd.DataFrame:
    """Implied share price (pence) across WACC and operating margin shifts.

    The margin shift is applied to EVERY forecast year, not just the last one.
    Columns are labelled by the resulting exit-year margin for readability.
    """
    grid = assumptions.sensitivity
    base_wacc = run_dcf(assumptions).wacc.wacc
    base_margin = assumptions.forecast.operating_margin[-1]

    data = {}
    for m_delta in grid.margin_deltas:
        column = f"exit margin = {base_margin + m_delta:.2%}"
        data[column] = [
            _safe_price(assumptions, wacc_delta=w_delta, margin_delta=m_delta)
            for w_delta in grid.wacc_deltas
        ]

    index = [f"WACC = {base_wacc + w:.2%}" for w in grid.wacc_deltas]
    return pd.DataFrame(data, index=index)


def lease_treatment_comparison(assumptions: Assumptions) -> pd.DataFrame:
    """Value the same business under IFRS 16 and pre-IFRS 16 lease treatment.

    This is the check that the two conventions are being applied consistently.
    Under "capitalised" the model adds back right-of-use depreciation and
    deducts lease liabilities as debt; under "expensed" it does neither. If the
    two land far apart, the right-of-use depreciation estimate or the lease
    liability figure is likely wrong.
    """
    rows = []
    for treatment in ("capitalised", "expensed"):
        variant = dataclasses.replace(assumptions, lease_treatment=treatment)
        try:
            output = run_dcf(variant)
        except ValueError:
            continue
        v = output.valuation
        rows.append(
            {
                "lease treatment": treatment,
                "net debt deducted": v.net_debt_deducted,
                "enterprise value": v.enterprise_value,
                "equity value": v.equity_value,
                "implied price (p)": v.implied_share_price_pence,
                "upside": v.upside_downside,
            }
        )
    return pd.DataFrame(rows).set_index("lease treatment")


def summary_statistics(tables: list[pd.DataFrame]) -> dict[str, float]:
    """Min, max and median implied price across every sensitivity cell."""
    values = np.concatenate([t.to_numpy(dtype=float).ravel() for t in tables])
    values = values[~np.isnan(values)]
    if values.size == 0:
        return {"min": float("nan"), "median": float("nan"), "max": float("nan")}
    return {
        "min": float(np.min(values)),
        "median": float(np.median(values)),
        "max": float(np.max(values)),
    }
