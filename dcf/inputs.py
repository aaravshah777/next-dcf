"""Typed containers for every DCF assumption, plus the YAML loader.

Keeping assumptions in dataclasses (rather than passing dictionaries around)
means a typo like ``risk_free_rt`` fails loudly at load time instead of
silently producing a valuation that is wrong by two percentage points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import yaml

__all__ = [
    "BaseYearFinancials",
    "ForecastDrivers",
    "WaccInputs",
    "TerminalValueInputs",
    "DiscountingInputs",
    "EquityBridge",
    "MarketData",
    "SensitivityGrid",
    "Assumptions",
    "load_assumptions",
]

VALID_LEASE_TREATMENTS = {"capitalised", "expensed"}


# --------------------------------------------------------------------------- #
# Individual assumption blocks
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BaseYearFinancials:
    """Last reported full financial year. The anchor for everything else."""

    revenue: float
    operating_profit: float
    profit_before_tax: float
    depreciation_amortisation: float
    capital_expenditure: float
    reported_free_cash_flow: float
    net_debt_excluding_leases: float
    lease_liabilities: float
    customer_receivables: float

    @property
    def operating_margin(self) -> float:
        return self.operating_profit / self.revenue

    @property
    def net_debt_including_leases(self) -> float:
        return self.net_debt_excluding_leases + self.lease_liabilities

    @property
    def credit_book_pct_revenue(self) -> float:
        """How much of revenue is tied up lending to Next's own customers."""
        return self.customer_receivables / self.revenue

    @property
    def capex_to_depreciation(self) -> float:
        """Well below 1x for a lease-heavy retailer. A flag, not an error."""
        return self.capital_expenditure / self.depreciation_amortisation


@dataclass(frozen=True)
class ForecastDrivers:
    """One value per explicit forecast year, except the tax rate."""

    years: Sequence[str]
    revenue_growth: Sequence[float]
    operating_margin: Sequence[float]
    depreciation_amortisation_pct_revenue: Sequence[float]
    rou_depreciation_pct_revenue: Sequence[float]
    cash_rent_pct_revenue: Sequence[float]
    capex_pct_revenue: Sequence[float]
    net_working_capital_pct_revenue: Sequence[float]
    effective_tax_rate: float

    def __post_init__(self) -> None:
        n = len(self.years)
        per_year = {
            "revenue_growth": self.revenue_growth,
            "operating_margin": self.operating_margin,
            "depreciation_amortisation_pct_revenue": self.depreciation_amortisation_pct_revenue,
            "rou_depreciation_pct_revenue": self.rou_depreciation_pct_revenue,
            "cash_rent_pct_revenue": self.cash_rent_pct_revenue,
            "capex_pct_revenue": self.capex_pct_revenue,
            "net_working_capital_pct_revenue": self.net_working_capital_pct_revenue,
        }
        for name, series in per_year.items():
            if len(series) != n:
                raise ValueError(
                    f"forecast.{name} has {len(series)} values but there are "
                    f"{n} forecast years. Every driver needs one value per year."
                )
        for i, (total, rou) in enumerate(
            zip(self.depreciation_amortisation_pct_revenue,
                self.rou_depreciation_pct_revenue)
        ):
            if rou > total:
                raise ValueError(
                    f"In forecast year {i + 1}, right-of-use depreciation "
                    f"({rou:.2%} of revenue) exceeds total D&A ({total:.2%}). "
                    "Lease depreciation is a component of D&A, not an addition."
                )
        for i, (rent, rou) in enumerate(
            zip(self.cash_rent_pct_revenue, self.rou_depreciation_pct_revenue)
        ):
            if rent < rou:
                raise ValueError(
                    f"In forecast year {i + 1}, cash rent ({rent:.2%} of revenue) "
                    f"is below right-of-use depreciation ({rou:.2%}). Cash rent "
                    "equals that depreciation plus the lease interest charge, so "
                    "it should be the larger of the two."
                )
        if not 0.0 <= self.effective_tax_rate < 1.0:
            raise ValueError("effective_tax_rate must be a decimal between 0 and 1.")

    @property
    def horizon(self) -> int:
        return len(self.years)


@dataclass(frozen=True)
class WaccInputs:
    risk_free_rate: float
    equity_risk_premium: float
    country_risk_premium: float
    levered_beta: float
    pre_tax_cost_of_debt: float
    marginal_tax_rate: float
    debt_measure: str = "net_debt"
    gross_debt: float = 0.0
    relever_beta: bool = False
    current_debt_to_equity: float = 0.0
    target_debt_to_equity: float = 0.0

    def __post_init__(self) -> None:
        if self.debt_measure not in {"net_debt", "gross_debt"}:
            raise ValueError("wacc.debt_measure must be 'net_debt' or 'gross_debt'.")
        if self.levered_beta <= 0:
            raise ValueError("wacc.levered_beta must be positive.")


@dataclass(frozen=True)
class TerminalValueInputs:
    method: str
    perpetuity_growth_rate: float
    exit_ev_ebitda_multiple: float

    def __post_init__(self) -> None:
        if self.method not in {"gordon_growth", "exit_multiple"}:
            raise ValueError(
                "terminal_value.method must be 'gordon_growth' or 'exit_multiple'."
            )


@dataclass(frozen=True)
class DiscountingInputs:
    mid_year_convention: bool = True


@dataclass(frozen=True)
class EquityBridge:
    shares_outstanding: float
    pension_deficit: float = 0.0
    minority_interests: float = 0.0
    investments: float = 0.0

    def __post_init__(self) -> None:
        if self.shares_outstanding <= 0:
            raise ValueError("equity_bridge.shares_outstanding must be positive.")


@dataclass(frozen=True)
class MarketData:
    share_price_pence: float

    @property
    def share_price_pounds(self) -> float:
        return self.share_price_pence / 100.0


@dataclass(frozen=True)
class SensitivityGrid:
    wacc_deltas: Sequence[float] = field(default_factory=lambda: [0.0])
    growth_deltas: Sequence[float] = field(default_factory=lambda: [0.0])
    margin_deltas: Sequence[float] = field(default_factory=lambda: [0.0])


@dataclass(frozen=True)
class Assumptions:
    """Everything the model needs, in one object."""

    meta: dict[str, Any]
    base: BaseYearFinancials
    forecast: ForecastDrivers
    lease_treatment: str
    wacc: WaccInputs
    terminal_value: TerminalValueInputs
    discounting: DiscountingInputs
    equity_bridge: EquityBridge
    market: MarketData
    sensitivity: SensitivityGrid

    @property
    def leases_are_debt(self) -> bool:
        """Under IFRS 16 treatment, lease liabilities belong in the debt total."""
        return self.lease_treatment == "capitalised"

    @property
    def net_debt(self) -> float:
        """Net debt on the basis implied by the chosen lease treatment."""
        if self.leases_are_debt:
            return self.base.net_debt_including_leases
        return self.base.net_debt_excluding_leases


# --------------------------------------------------------------------------- #
# Loader
# --------------------------------------------------------------------------- #
def load_assumptions(path: str | Path = "assumptions.yaml") -> Assumptions:
    """Read the YAML assumptions file and return a validated ``Assumptions``."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find '{path}'. Run the model from the repository root, "
            "or pass --assumptions with an explicit path."
        )

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    required = {
        "base_year_financials",
        "forecast",
        "wacc",
        "terminal_value",
        "equity_bridge",
        "market",
    }
    missing = required - set(raw)
    if missing:
        raise KeyError(f"assumptions.yaml is missing section(s): {sorted(missing)}")

    lease_treatment = raw.get("lease_treatment", "capitalised")
    if lease_treatment not in VALID_LEASE_TREATMENTS:
        raise ValueError(
            f"lease_treatment must be one of {sorted(VALID_LEASE_TREATMENTS)}, "
            f"got '{lease_treatment}'."
        )

    return Assumptions(
        meta=raw.get("meta", {}),
        base=BaseYearFinancials(**raw["base_year_financials"]),
        forecast=ForecastDrivers(**raw["forecast"]),
        lease_treatment=lease_treatment,
        wacc=WaccInputs(**raw["wacc"]),
        terminal_value=TerminalValueInputs(**raw["terminal_value"]),
        discounting=DiscountingInputs(**raw.get("discounting", {})),
        equity_bridge=EquityBridge(**raw["equity_bridge"]),
        market=MarketData(**raw["market"]),
        sensitivity=SensitivityGrid(**raw.get("sensitivity", {})),
    )
