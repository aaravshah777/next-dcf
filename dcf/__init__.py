"""A transparent, five-step discounted cash flow model for NEXT plc.

    from dcf import load_assumptions, run_dcf

    output = run_dcf(load_assumptions("assumptions.yaml"))
    print(output.valuation.implied_share_price_pence)

The five steps map one-to-one onto the modules:

    1. forecast.py    forecast unlevered free cash flow
    2. wacc.py        weighted average cost of capital
    3. terminal.py    terminal value
    4. valuation.py   discount the flows and the terminal value
    5. valuation.py   bridge enterprise value to an implied share price

Everything is in sterling throughout; there is no currency conversion.
"""

from .forecast import ForecastResult, forecast_free_cash_flow
from .inputs import Assumptions, load_assumptions
from .model import DcfOutput, run_dcf
from .sensitivity import (
    lease_treatment_comparison,
    summary_statistics,
    wacc_vs_growth,
    wacc_vs_margin,
)
from .terminal import (
    TerminalValueResult,
    compute_terminal_value,
    exit_multiple_terminal_value,
    gordon_growth_terminal_value,
)
from .valuation import ValuationResult, discount_cash_flows, discount_factor, value_equity
from .wacc import WaccResult, compute_wacc, cost_of_equity, relever_beta, unlever_beta

__version__ = "1.0.0"

__all__ = [
    "Assumptions",
    "DcfOutput",
    "ForecastResult",
    "TerminalValueResult",
    "ValuationResult",
    "WaccResult",
    "compute_terminal_value",
    "compute_wacc",
    "cost_of_equity",
    "discount_cash_flows",
    "discount_factor",
    "exit_multiple_terminal_value",
    "forecast_free_cash_flow",
    "gordon_growth_terminal_value",
    "lease_treatment_comparison",
    "load_assumptions",
    "relever_beta",
    "run_dcf",
    "summary_statistics",
    "unlever_beta",
    "value_equity",
    "wacc_vs_growth",
    "wacc_vs_margin",
]
