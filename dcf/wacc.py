"""STEP 2 — Weighted average cost of capital.

    WACC = E/(D+E) * Ke  +  D/(D+E) * Kd * (1 - t)

Cost of equity comes from the CAPM:

    Ke = Rf + Beta * ERP + CRP

Four points that cost marks in exams, all handled here:

1. CURRENCY MATCHING. Next reports in sterling, so the risk-free rate is the
   10-year GILT. Using a US Treasury or a Bund because the number looks more
   familiar is a currency mismatch.

2. THE GILT IS UNUSUALLY HIGH RIGHT NOW. At around 5.5% it is near its highest
   since 2008. That feeds straight into the cost of equity and produces a WACC
   well above the 8%-ish figure most textbooks use as an illustration. Do not
   "correct" it towards the textbook number — the whole point of CAPM is that
   the discount rate moves with the market. But do say in your write-up that
   the valuation is unusually sensitive to this one input today.

3. MARKET-VALUE WEIGHTS. E is market capitalisation, not book equity. Book
   equity is an accounting residual and has nothing to do with required returns.
   Next's book equity (c.£1.8bn) is about a tenth of its market value, so this
   choice is not a technicality.

4. THE TAX SHIELD GOES ON DEBT ONLY. Interest is deductible, dividends are not.
   That is the whole reason debt is the cheaper source of capital.

A note on beta: 1.05 reflects discretionary clothing retail, which is more
cyclical than a consumer staple. A defensive grocer would sit nearer 0.6-0.7.
Estimating it yourself from five years of weekly returns against the FTSE
All-Share would be a genuine improvement on assuming it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .inputs import EquityBridge, MarketData, WaccInputs

__all__ = ["WaccResult", "unlever_beta", "relever_beta", "cost_of_equity", "compute_wacc"]


@dataclass(frozen=True)
class WaccResult:
    cost_of_equity: float
    pre_tax_cost_of_debt: float
    after_tax_cost_of_debt: float
    beta_used: float
    market_value_equity: float
    market_value_debt: float
    weight_equity: float
    weight_debt: float
    wacc: float


def unlever_beta(levered_beta: float, debt_to_equity: float, tax_rate: float) -> float:
    """Hamada: strip financial risk out of an observed equity beta.

        Bu = Bl / (1 + (1 - t) * D/E)
    """
    return levered_beta / (1.0 + (1.0 - tax_rate) * debt_to_equity)


def relever_beta(unlevered: float, debt_to_equity: float, tax_rate: float) -> float:
    """Hamada, in reverse: add back the financial risk of a target structure.

        Bl = Bu * (1 + (1 - t) * D/E)
    """
    return unlevered * (1.0 + (1.0 - tax_rate) * debt_to_equity)


def cost_of_equity(
    risk_free_rate: float,
    beta: float,
    equity_risk_premium: float,
    country_risk_premium: float = 0.0,
) -> float:
    """CAPM, with an optional additive country risk premium."""
    return risk_free_rate + beta * equity_risk_premium + country_risk_premium


def compute_wacc(
    wacc_inputs: WaccInputs,
    bridge: EquityBridge,
    market: MarketData,
    net_debt: float,
    *,
    wacc_delta: float = 0.0,
) -> WaccResult:
    """Compute the WACC from market data and the CAPM inputs.

    ``net_debt`` is passed in rather than read off the bridge because it
    depends on the lease treatment, which is a model-level choice. Keeping that
    decision in one place stops the WACC and the equity bridge drifting apart.

    ``wacc_delta`` is a parallel shift used by the sensitivity analysis. It is
    applied to the final WACC rather than to any single component, because the
    point of that table is "what if my whole discount rate is wrong", not "what
    if beta specifically is wrong".
    """
    # --- Cost of equity ---------------------------------------------------- #
    beta = wacc_inputs.levered_beta
    if wacc_inputs.relever_beta:
        unlevered = unlever_beta(
            wacc_inputs.levered_beta,
            wacc_inputs.current_debt_to_equity,
            wacc_inputs.marginal_tax_rate,
        )
        beta = relever_beta(
            unlevered,
            wacc_inputs.target_debt_to_equity,
            wacc_inputs.marginal_tax_rate,
        )

    ke = cost_of_equity(
        wacc_inputs.risk_free_rate,
        beta,
        wacc_inputs.equity_risk_premium,
        wacc_inputs.country_risk_premium,
    )

    # --- Cost of debt ------------------------------------------------------ #
    kd_pre_tax = wacc_inputs.pre_tax_cost_of_debt
    kd_after_tax = kd_pre_tax * (1.0 - wacc_inputs.marginal_tax_rate)

    # --- Market-value weights ---------------------------------------------- #
    market_value_equity = market.share_price_pounds * bridge.shares_outstanding
    market_value_debt = (
        net_debt if wacc_inputs.debt_measure == "net_debt" else wacc_inputs.gross_debt
    )

    total_capital = market_value_equity + market_value_debt
    if total_capital <= 0:
        raise ValueError("Total capital is non-positive; check price and debt inputs.")

    weight_equity = market_value_equity / total_capital
    weight_debt = market_value_debt / total_capital

    wacc = weight_equity * ke + weight_debt * kd_after_tax + wacc_delta

    return WaccResult(
        cost_of_equity=ke,
        pre_tax_cost_of_debt=kd_pre_tax,
        after_tax_cost_of_debt=kd_after_tax,
        beta_used=beta,
        market_value_equity=market_value_equity,
        market_value_debt=market_value_debt,
        weight_equity=weight_equity,
        weight_debt=weight_debt,
        wacc=wacc,
    )
