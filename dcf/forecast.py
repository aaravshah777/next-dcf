"""STEP 1 — Forecast unlevered free cash flow.

The quantity we discount is FREE CASH FLOW TO THE FIRM (FCFF), also called
unlevered free cash flow: the cash the business throws off before any payment to
lenders or shareholders. It must be unlevered because we discount it at the
WACC, which is the blended required return of all capital providers. Discounting
a cash flow already net of interest at the WACC double-counts the cost of debt.

The build:

    Revenue
  x Operating margin
  = EBIT
  x (1 - effective tax rate)
  = NOPAT, net operating profit after tax
  + Depreciation & amortisation      <- non-cash, added back (see lease note)
  - Capital expenditure              <- cash out, not in the P&L
  - Increase in net working capital  <- cash tied up in the balance sheet
  = Unlevered free cash flow

TWO THINGS THAT MAKE NEXT DIFFERENT FROM A TEXTBOOK EXAMPLE
-----------------------------------------------------------

1. LEASES. Next's D&A is roughly 4.7% of revenue against capex of 2.0%. That
   gap is right-of-use asset depreciation under IFRS 16. Which part of D&A gets
   added back depends on the lease treatment:

       "capitalised"  EBIT after right-of-use depreciation, add back ALL D&A,
                      and deduct lease liabilities as debt
       "expensed"     EBIT after full cash rent instead, add back only
                      NON-LEASE D&A, and ignore lease liabilities

   Adding back lease depreciation while ignoring the lease liability takes the
   benefit of the lease and none of the cost. On Next that error is worth well
   over £1bn of phantom equity value.

2. THE CREDIT BOOK. Next lends to its own customers through Next Finance, and
   the resulting receivables (c.23% of revenue) sit in working capital. Net
   working capital is therefore strongly POSITIVE, so growth CONSUMES cash. A
   grocer or an FMCG group has the opposite profile, where growth releases cash
   because suppliers are paid after customers pay. Do not carry an intuition
   from one to the other.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .inputs import BaseYearFinancials, ForecastDrivers

__all__ = ["ForecastResult", "forecast_free_cash_flow"]


@dataclass(frozen=True)
class ForecastResult:
    """The forecast as a tidy table plus the series the later steps need."""

    table: pd.DataFrame
    lease_treatment: str

    @property
    def years(self) -> list[str]:
        return list(self.table["year"])

    @property
    def free_cash_flow(self) -> list[float]:
        return list(self.table["free_cash_flow"])

    @property
    def terminal_year_fcf(self) -> float:
        return float(self.table["free_cash_flow"].iloc[-1])

    @property
    def terminal_year_ebitda(self) -> float:
        return float(self.table["ebitda"].iloc[-1])


def forecast_free_cash_flow(
    base: BaseYearFinancials,
    drivers: ForecastDrivers,
    *,
    lease_treatment: str = "capitalised",
    growth_delta: float = 0.0,
    margin_delta: float = 0.0,
) -> ForecastResult:
    """Build the explicit-period unlevered FCF forecast.

    Parameters
    ----------
    base
        Last reported financial year, used to seed revenue and opening NWC.
    drivers
        Per-year growth, margin, capex, D&A and working capital assumptions.
    lease_treatment
        "capitalised" (IFRS 16) adds back all D&A; "expensed" adds back only
        the non-lease portion. Must match the equity bridge, which is enforced
        by both being driven from the same assumptions object.
    growth_delta, margin_delta
        Parallel shifts applied to every forecast year. Used by the sensitivity
        analysis so it can flex the operating case without editing the YAML.
    """
    tax = drivers.effective_tax_rate

    # Opening net working capital, on the same %-of-revenue basis as the
    # forecast, so the first year's movement is measured consistently.
    previous_revenue = base.revenue
    previous_nwc = base.revenue * drivers.net_working_capital_pct_revenue[0]

    rows: list[dict[str, float | str]] = []

    for i, year in enumerate(drivers.years):
        growth = drivers.revenue_growth[i] + growth_delta
        margin = drivers.operating_margin[i] + margin_delta

        revenue = previous_revenue * (1.0 + growth)
        ebit_ifrs16 = revenue * margin

        total_d_and_a = revenue * drivers.depreciation_amortisation_pct_revenue[i]
        rou_d_and_a = revenue * drivers.rou_depreciation_pct_revenue[i]
        cash_rent = revenue * drivers.cash_rent_pct_revenue[i]

        # The lease treatment decides two things at once, and they must move
        # together: what EBIT is measured after, and how much depreciation is a
        # genuine non-cash add-back.
        if lease_treatment == "capitalised":
            # IFRS 16. EBIT is already after right-of-use depreciation, and all
            # depreciation is non-cash, so all of it is added back. The cash
            # cost of the leases appears instead as a liability in the bridge.
            ebit = ebit_ifrs16
            d_and_a_added_back = total_d_and_a
        else:
            # Pre-IFRS 16. Rent is an operating cost, so add back the
            # right-of-use depreciation IFRS 16 charged and deduct the full
            # cash rent in its place. Cash rent exceeds that depreciation by
            # the lease interest, which IFRS 16 reports below EBIT.
            ebit = ebit_ifrs16 + rou_d_and_a - cash_rent
            d_and_a_added_back = total_d_and_a - rou_d_and_a

        nopat = ebit * (1.0 - tax)
        capex = revenue * drivers.capex_pct_revenue[i]

        nwc = revenue * drivers.net_working_capital_pct_revenue[i]
        change_in_nwc = nwc - previous_nwc  # positive = cash absorbed

        fcf = nopat + d_and_a_added_back - capex - change_in_nwc

        rows.append(
            {
                "year": year,
                "revenue": revenue,
                "revenue_growth": growth,
                "operating_margin": margin,
                "ebit": ebit,
                "ebitda": ebit + total_d_and_a,
                "tax_on_ebit": ebit * tax,
                "nopat": nopat,
                "depreciation_amortisation": total_d_and_a,
                "rou_depreciation": rou_d_and_a,
                "cash_rent": cash_rent,
                "d_and_a_added_back": d_and_a_added_back,
                "capital_expenditure": capex,
                "net_working_capital": nwc,
                "change_in_net_working_capital": change_in_nwc,
                "free_cash_flow": fcf,
            }
        )

        previous_revenue = revenue
        previous_nwc = nwc

    return ForecastResult(table=pd.DataFrame(rows), lease_treatment=lease_treatment)
