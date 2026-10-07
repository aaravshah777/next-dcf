"""Orchestration: run all five steps end to end.

``run_dcf`` is deliberately thin. Each step lives in its own module so you can
import one piece in isolation (for a tutorial question on WACC, say) without
dragging the whole model along.

The one piece of real logic here is that the LEASE TREATMENT is read once and
passed to both the forecast and the equity bridge, so the D&A add-back and the
net debt deduction can never disagree with each other.
"""

from __future__ import annotations

from dataclasses import dataclass

from .forecast import ForecastResult, forecast_free_cash_flow
from .inputs import Assumptions
from .terminal import TerminalValueResult, compute_terminal_value
from .valuation import ValuationResult, value_equity
from .wacc import WaccResult, compute_wacc

__all__ = ["DcfOutput", "run_dcf"]


@dataclass(frozen=True)
class DcfOutput:
    assumptions: Assumptions
    forecast: ForecastResult
    wacc: WaccResult
    terminal: TerminalValueResult
    valuation: ValuationResult


def run_dcf(
    assumptions: Assumptions,
    *,
    wacc_delta: float = 0.0,
    growth_delta: float = 0.0,
    margin_delta: float = 0.0,
    terminal_growth_delta: float = 0.0,
) -> DcfOutput:
    """Run the full model.

    The ``*_delta`` arguments shift an assumption without touching the YAML
    file. The sensitivity analysis uses them; a normal run leaves them at zero.
    """
    # Net debt depends on the lease treatment, and both the WACC weights and
    # the equity bridge must use the same figure.
    net_debt = assumptions.net_debt

    # Step 1 — forecast unlevered free cash flow
    forecast = forecast_free_cash_flow(
        assumptions.base,
        assumptions.forecast,
        lease_treatment=assumptions.lease_treatment,
        growth_delta=growth_delta,
        margin_delta=margin_delta,
    )

    # Step 2 — weighted average cost of capital
    wacc = compute_wacc(
        assumptions.wacc,
        assumptions.equity_bridge,
        assumptions.market,
        net_debt,
        wacc_delta=wacc_delta,
    )

    # Step 3 — terminal value
    terminal = compute_terminal_value(
        forecast.terminal_year_fcf,
        forecast.terminal_year_ebitda,
        wacc.wacc,
        method=assumptions.terminal_value.method,
        perpetuity_growth_rate=(
            assumptions.terminal_value.perpetuity_growth_rate + terminal_growth_delta
        ),
        exit_ev_ebitda_multiple=assumptions.terminal_value.exit_ev_ebitda_multiple,
    )

    # Steps 4 and 5 — discount, then bridge to the implied share price
    valuation = value_equity(
        forecast,
        terminal,
        wacc.wacc,
        assumptions.equity_bridge,
        assumptions.market,
        net_debt,
        mid_year_convention=assumptions.discounting.mid_year_convention,
    )

    return DcfOutput(
        assumptions=assumptions,
        forecast=forecast,
        wacc=wacc,
        terminal=terminal,
        valuation=valuation,
    )
