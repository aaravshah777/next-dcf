"""STEP 3 — Terminal value.

Beyond the explicit forecast horizon we stop forecasting year by year and
capitalise the final cash flow instead. For a mature business this is normally
60-85% of total enterprise value, which is exactly why the terminal assumptions
deserve more scrutiny than the year-by-year forecast, not less.

Two standard methods:

GORDON GROWTH (perpetuity growth)

    TV = FCF_n * (1 + g) / (WACC - g)

    The numerator grows the final forecast cash flow one more year, because the
    perpetuity formula values a stream that STARTS one period after the
    valuation point. Forgetting the (1+g) is the single most common slip.

    g must be below the long-run nominal growth rate of the economy. A firm
    growing faster than its economy forever would eventually become the whole
    economy. For a UK retailer, at or modestly above the 2% inflation target is
    defensible; anything approaching 4% is not.

EXIT MULTIPLE

    TV = EBITDA_n * multiple

    Assumes the business is sold at the end of the horizon at a multiple in
    line with comparable companies. Retail multiples are structurally lower
    than consumer staples, typically 7-9x rather than 11-13x, because the
    earnings are more cyclical and more exposed to the high street.

    CAUTION FOR LEASE-HEAVY RETAILERS: if the EBITDA used is post-IFRS 16 (so
    rent sits in depreciation and interest rather than in operating costs),
    the multiple must also be a post-IFRS 16 multiple. Comparing a post-IFRS 16
    EBITDA with a multiple drawn from pre-IFRS 16 peers overstates the terminal
    value substantially, because post-IFRS 16 EBITDA is the larger number.

The functions below also run the cross-checks in reverse — what exit multiple
your growth rate implies, and what growth rate your exit multiple implies.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "TerminalValueResult",
    "gordon_growth_terminal_value",
    "exit_multiple_terminal_value",
    "implied_exit_multiple",
    "implied_perpetuity_growth",
    "compute_terminal_value",
]


@dataclass(frozen=True)
class TerminalValueResult:
    method: str
    terminal_value: float
    perpetuity_growth_rate: float  # the rate actually used, after any override
    gordon_growth_value: float
    exit_multiple_value: float
    implied_exit_ev_ebitda: float
    implied_perpetuity_growth: float


def gordon_growth_terminal_value(
    final_year_fcf: float, wacc: float, growth: float
) -> float:
    """TV = FCF_n * (1 + g) / (WACC - g)."""
    if wacc <= growth:
        raise ValueError(
            f"Perpetuity growth ({growth:.2%}) must be below the WACC "
            f"({wacc:.2%}). Otherwise the formula returns a negative or "
            "infinite value, which is a mathematical artefact, not a valuation."
        )
    return final_year_fcf * (1.0 + growth) / (wacc - growth)


def exit_multiple_terminal_value(final_year_ebitda: float, multiple: float) -> float:
    """TV = EBITDA_n * exit multiple."""
    if multiple <= 0:
        raise ValueError("Exit multiple must be positive.")
    return final_year_ebitda * multiple


def implied_exit_multiple(terminal_value: float, final_year_ebitda: float) -> float:
    """What EV/EBITDA does my perpetuity growth rate actually imply?

    If this comes out far above the multiple the shares trade on today, the
    terminal growth rate is carrying the valuation.
    """
    if final_year_ebitda <= 0:
        return float("nan")
    return terminal_value / final_year_ebitda


def implied_perpetuity_growth(
    terminal_value: float, final_year_fcf: float, wacc: float
) -> float:
    """Invert Gordon Growth: what growth rate does my exit multiple imply?

        TV = FCF*(1+g)/(WACC-g)  =>  g = (TV*WACC - FCF) / (TV + FCF)
    """
    denominator = terminal_value + final_year_fcf
    if denominator == 0:
        return float("nan")
    return (terminal_value * wacc - final_year_fcf) / denominator


def compute_terminal_value(
    final_year_fcf: float,
    final_year_ebitda: float,
    wacc: float,
    *,
    method: str = "gordon_growth",
    perpetuity_growth_rate: float = 0.025,
    exit_ev_ebitda_multiple: float = 8.0,
) -> TerminalValueResult:
    """Compute the terminal value under both methods and return the cross-checks."""
    gordon = gordon_growth_terminal_value(final_year_fcf, wacc, perpetuity_growth_rate)
    exit_value = exit_multiple_terminal_value(final_year_ebitda, exit_ev_ebitda_multiple)

    chosen = gordon if method == "gordon_growth" else exit_value

    return TerminalValueResult(
        method=method,
        terminal_value=chosen,
        perpetuity_growth_rate=perpetuity_growth_rate,
        gordon_growth_value=gordon,
        exit_multiple_value=exit_value,
        implied_exit_ev_ebitda=implied_exit_multiple(chosen, final_year_ebitda),
        implied_perpetuity_growth=implied_perpetuity_growth(
            exit_value, final_year_fcf, wacc
        ),
    )
