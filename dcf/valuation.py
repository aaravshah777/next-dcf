"""STEPS 4 & 5 — Discount the cash flows, then bridge to an implied share price.

STEP 4: DISCOUNTING

    PV = CF_t / (1 + WACC)^t

    The terminal value is discounted at the SAME exponent as the final forecast
    year, not one year further. It is already a value measured as at the end of
    year n, so discounting it at n+1 would double-discount a year.

    Mid-year convention: cash arrives throughout the year, not in a lump on the
    year-end date, so flows are discounted at t - 0.5. It lifts the valuation by
    roughly (1 + WACC)^0.5. Both conventions are accepted; just say which you
    used.

STEP 5: THE EQUITY BRIDGE

    Enterprise value          value of the operating business to all investors
      - Net debt              lenders are paid before shareholders
      - Lease liabilities     under IFRS 16, included in net debt (see below)
      - Pension deficit       a debt-like claim on the firm
      - Minority interests    part of the consolidated business you don't own
      + Investments           stakes not captured in the forecast cash flow
    = Equity value
      / Diluted shares
    = Implied value per share

THE LEASE CONSISTENCY RULE, ENFORCED HERE
-----------------------------------------
Whether lease liabilities are deducted is NOT a free choice at this stage. It
is determined by how the forecast treated right-of-use depreciation:

    forecast added back ALL D&A  ->  lease liabilities MUST be deducted
    forecast added back only non-lease D&A  ->  they must NOT be

Both flow from a single `lease_treatment` setting so they cannot drift apart.
Getting this wrong in either direction misstates Next's equity value by over
£1bn.

A NOTE ON NEXT'S NET DEBT
-------------------------
Most of Next's borrowing funds the Next Finance customer receivables book
rather than the retail operation. We still deduct it in full, because the
interest income those receivables earn is already inside forecast revenue. The
alternative is to carve the credit business out entirely and value it
separately — more rigorous, considerably more work, and you must not do half of
each. Deducting the debt while excluding the interest income would double-count
the cost of the credit book.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .forecast import ForecastResult
from .inputs import EquityBridge, MarketData
from .terminal import TerminalValueResult

__all__ = ["ValuationResult", "discount_factor", "discount_cash_flows", "value_equity"]


@dataclass(frozen=True)
class ValuationResult:
    """Everything downstream of the forecast, ready to print or export."""

    discounted_table: pd.DataFrame
    pv_explicit_fcf: float
    pv_terminal_value: float
    enterprise_value: float
    equity_value: float
    net_debt_deducted: float
    implied_share_price_pounds: float
    implied_share_price_pence: float
    market_share_price_pence: float
    upside_downside: float
    terminal_value_share_of_ev: float

    @property
    def verdict(self) -> str:
        if self.upside_downside > 0.15:
            return "UNDERVALUED on these assumptions"
        if self.upside_downside < -0.15:
            return "OVERVALUED on these assumptions"
        return "BROADLY FAIRLY VALUED on these assumptions"


def discount_factor(wacc: float, period: float) -> float:
    """1 / (1 + WACC)^period."""
    return 1.0 / ((1.0 + wacc) ** period)


def discount_cash_flows(
    forecast: ForecastResult,
    wacc: float,
    *,
    mid_year_convention: bool = True,
) -> pd.DataFrame:
    """Attach discount periods, factors and present values to the forecast."""
    table = forecast.table.copy()

    # Period 1 is the first forecast year. Mid-year shifts each by half a year.
    periods = [float(i + 1) for i in range(len(table))]
    if mid_year_convention:
        periods = [p - 0.5 for p in periods]

    table["discount_period"] = periods
    table["discount_factor"] = [discount_factor(wacc, p) for p in periods]
    table["pv_free_cash_flow"] = table["free_cash_flow"] * table["discount_factor"]
    return table


def value_equity(
    forecast: ForecastResult,
    terminal: TerminalValueResult,
    wacc: float,
    bridge: EquityBridge,
    market: MarketData,
    net_debt: float,
    *,
    mid_year_convention: bool = True,
) -> ValuationResult:
    """Run step 4 and step 5 and return the full valuation.

    ``net_debt`` already reflects the lease treatment: it includes lease
    liabilities under IFRS 16 ("capitalised") and excludes them otherwise.
    """
    table = discount_cash_flows(forecast, wacc, mid_year_convention=mid_year_convention)

    pv_explicit = float(table["pv_free_cash_flow"].sum())

    # The terminal value sits at the END of the final forecast year, so it is
    # discounted over the full number of years regardless of the mid-year
    # convention applied to the flows within those years.
    terminal_period = float(len(table))
    pv_terminal = terminal.terminal_value * discount_factor(wacc, terminal_period)

    enterprise_value = pv_explicit + pv_terminal

    equity_value = (
        enterprise_value
        - net_debt
        - bridge.pension_deficit
        - bridge.minority_interests
        + bridge.investments
    )

    implied_pounds = equity_value / bridge.shares_outstanding
    implied_pence = implied_pounds * 100.0

    upside = implied_pence / market.share_price_pence - 1.0

    return ValuationResult(
        discounted_table=table,
        pv_explicit_fcf=pv_explicit,
        pv_terminal_value=pv_terminal,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        net_debt_deducted=net_debt,
        implied_share_price_pounds=implied_pounds,
        implied_share_price_pence=implied_pence,
        market_share_price_pence=market.share_price_pence,
        upside_downside=upside,
        terminal_value_share_of_ev=(
            pv_terminal / enterprise_value if enterprise_value else float("nan")
        ),
    )
