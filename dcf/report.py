"""Console output and CSV/chart export."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .model import DcfOutput

__all__ = ["print_report", "export_csv", "export_chart"]

LINE = "=" * 78
THIN = "-" * 78


def _m(value: float) -> str:
    return f"{value:>12,.0f}"


def _pct(value: float) -> str:
    return f"{value:>11.2%}"


def print_report(
    output: DcfOutput, sensitivities: dict[str, pd.DataFrame] | None = None
) -> None:
    """Print the whole model to stdout, step by step."""
    a = output.assumptions
    meta = a.meta
    name = meta.get("company", "Company")
    ticker = meta.get("ticker", "")
    ccy = meta.get("currency", "GBP")

    print()
    print(LINE)
    print(f" DISCOUNTED CASH FLOW VALUATION — {name} ({ticker})".center(78))
    print(f" All figures in {ccy} millions unless stated".center(78))
    print(LINE)

    print(f"\nBase year: {meta.get('base_year', 'n/a')}")
    print(f"Lease treatment: {a.lease_treatment}", end="")
    if a.leases_are_debt:
        print("  (IFRS 16: all D&A added back, lease liabilities treated as debt)")
    else:
        print("  (pre-IFRS 16: lease depreciation not added back, leases not debt)")

    # ---------------------------------------------------------------- step 1
    print("\nSTEP 1 — FORECAST UNLEVERED FREE CASH FLOW")
    print(THIN)
    t = output.forecast.table
    years = "".join(f"{str(y):>13}" for y in t["year"])
    print(f"{'':<34}{years}")
    rows = [
        ("Revenue", "revenue", _m),
        ("  growth %", "revenue_growth", _pct),
        ("EBIT", "ebit", _m),
        ("  operating margin %", "operating_margin", _pct),
        ("Less: tax on EBIT", "tax_on_ebit", _m),
        ("NOPAT", "nopat", _m),
        ("Add: D&A added back", "d_and_a_added_back", _m),
        ("  of which total D&A", "depreciation_amortisation", _m),
        ("  of which lease depreciation", "rou_depreciation", _m),
        ("Less: capital expenditure", "capital_expenditure", _m),
        ("Less: increase in work. capital", "change_in_net_working_capital", _m),
        ("UNLEVERED FREE CASH FLOW", "free_cash_flow", _m),
    ]
    for label, column, fmt in rows:
        cells = "".join(f"{fmt(v):>13}" for v in t[column])
        print(f"{label:<34}{cells}")

    # ---------------------------------------------------------------- step 2
    w = output.wacc
    print("\nSTEP 2 — WEIGHTED AVERAGE COST OF CAPITAL")
    print(THIN)
    print(f"{'Risk-free rate (10y gilt)':<42}{a.wacc.risk_free_rate:>10.2%}")
    print(f"{'Equity risk premium':<42}{a.wacc.equity_risk_premium:>10.2%}")
    if a.wacc.country_risk_premium:
        print(f"{'Country risk premium':<42}{a.wacc.country_risk_premium:>10.2%}")
    print(f"{'Levered beta':<42}{w.beta_used:>10.2f}")
    print(f"{'  Cost of equity (CAPM)':<42}{w.cost_of_equity:>10.2%}")
    print(f"{'Pre-tax cost of debt':<42}{w.pre_tax_cost_of_debt:>10.2%}")
    print(f"{'  After-tax cost of debt':<42}{w.after_tax_cost_of_debt:>10.2%}")
    print(f"{'Market value of equity':<42}{w.market_value_equity:>10,.0f}")
    print(f"{'Market value of debt':<42}{w.market_value_debt:>10,.0f}")
    print(f"{'  Weight of equity':<42}{w.weight_equity:>10.2%}")
    print(f"{'  Weight of debt':<42}{w.weight_debt:>10.2%}")
    print(f"{'WACC':<42}{w.wacc:>10.2%}")

    # ---------------------------------------------------------------- step 3
    tv = output.terminal
    print("\nSTEP 3 — TERMINAL VALUE")
    print(THIN)
    print(f"{'Method used':<42}{tv.method:>10}")
    print(f"{'Final year free cash flow':<42}{output.forecast.terminal_year_fcf:>10,.0f}")
    print(f"{'Perpetuity growth rate':<42}{tv.perpetuity_growth_rate:>10.2%}")
    print(f"{'  Gordon growth terminal value':<42}{tv.gordon_growth_value:>10,.0f}")
    print(f"{'Final year EBITDA':<42}{output.forecast.terminal_year_ebitda:>10,.0f}")
    print(f"{'Exit EV/EBITDA multiple':<42}{a.terminal_value.exit_ev_ebitda_multiple:>10.1f}x")
    print(f"{'  Exit multiple terminal value':<42}{tv.exit_multiple_value:>10,.0f}")
    print(f"{'TERMINAL VALUE':<42}{tv.terminal_value:>10,.0f}")
    print("\n  Cross-checks:")
    print(f"{'  EV/EBITDA implied by chosen method':<42}{tv.implied_exit_ev_ebitda:>10.1f}x")
    print(f"{'  Growth implied by exit multiple':<42}{tv.implied_perpetuity_growth:>10.2%}")

    # ---------------------------------------------------------------- step 4
    v = output.valuation
    print("\nSTEP 4 — DISCOUNT THE CASH FLOWS")
    print(THIN)
    convention = "mid-year" if a.discounting.mid_year_convention else "year-end"
    print(f"Discounting convention: {convention}\n")
    d = v.discounted_table
    print(f"{'Year':<10}{'FCF':>14}{'Period':>10}{'Factor':>12}{'PV of FCF':>16}")
    for _, row in d.iterrows():
        print(
            f"{str(row['year']):<10}{row['free_cash_flow']:>14,.0f}"
            f"{row['discount_period']:>10.1f}{row['discount_factor']:>12.4f}"
            f"{row['pv_free_cash_flow']:>16,.0f}"
        )
    print(f"\n{'PV of explicit forecast FCF':<42}{v.pv_explicit_fcf:>10,.0f}")
    print(f"{'PV of terminal value':<42}{v.pv_terminal_value:>10,.0f}")
    print(f"{'ENTERPRISE VALUE':<42}{v.enterprise_value:>10,.0f}")
    print(f"{'  Terminal value as % of EV':<42}{v.terminal_value_share_of_ev:>10.1%}")

    # ---------------------------------------------------------------- step 5
    b = a.equity_bridge
    print("\nSTEP 5 — EQUITY BRIDGE AND IMPLIED SHARE PRICE")
    print(THIN)
    print(f"{'Enterprise value':<42}{v.enterprise_value:>10,.0f}")
    if a.leases_are_debt:
        print(f"{'Less: net debt excluding leases':<42}{-a.base.net_debt_excluding_leases:>10,.0f}")
        print(f"{'Less: lease liabilities (IFRS 16)':<42}{-a.base.lease_liabilities:>10,.0f}")
    else:
        print(f"{'Less: net debt (leases excluded)':<42}{-a.base.net_debt_excluding_leases:>10,.0f}")
    print(f"{'Less: pension deficit':<42}{-b.pension_deficit:>10,.0f}")
    print(f"{'Less: minority interests':<42}{-b.minority_interests:>10,.0f}")
    print(f"{'Add: investments':<42}{b.investments:>10,.0f}")
    print(f"{'EQUITY VALUE':<42}{v.equity_value:>10,.0f}")
    print(f"{'Diluted shares outstanding (m)':<42}{b.shares_outstanding:>10,.2f}")
    print()
    print(f"{'Implied value per share':<42}{'£' + format(v.implied_share_price_pounds, ',.2f'):>10}")
    print(f"{'Implied value per share (pence)':<42}{v.implied_share_price_pence:>10,.0f}p")
    print(f"{'Current market price (pence)':<42}{v.market_share_price_pence:>10,.0f}p")
    print(f"{'Upside / (downside)':<42}{v.upside_downside:>10.1%}")
    print(f"\n  >>> {v.verdict}")

    # ---------------------------------------------------------------- extras
    if sensitivities:
        print("\nSENSITIVITY ANALYSIS")
        print(THIN)
        for title, table in sensitivities.items():
            print(f"\n{title}")
            if "lease" in title.lower():
                print(table.to_string(float_format=lambda x: f"{x:,.2f}"))
            else:
                print(table.to_string(float_format=lambda x: f"{x:,.0f}p"))

    print()
    print(LINE)
    print(" A DCF is an argument, not an answer. Defend the assumptions. ".center(78))
    print(LINE)
    print()


def export_csv(
    output: DcfOutput, sensitivities: dict[str, pd.DataFrame], out_dir: Path
) -> list[Path]:
    """Write the forecast, the discounted table and each sensitivity grid to CSV."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    paths = {
        "fcf_forecast.csv": output.forecast.table,
        "discounted_cash_flows.csv": output.valuation.discounted_table,
    }
    for i, (title, table) in enumerate(sensitivities.items(), start=1):
        # Keep filenames shell-safe: letters, digits and underscores only.
        slug = "".join(c if c.isalnum() else "_" for c in title.lower())
        slug = "_".join(part for part in slug.split("_") if part)[:40]
        paths[f"sensitivity_{i}_{slug}.csv"] = table

    for filename, frame in paths.items():
        path = out_dir / filename
        frame.to_csv(path, index=filename.startswith("sensitivity"))
        written.append(path)

    v = output.valuation
    summary = pd.DataFrame(
        [
            {
                "lease_treatment": output.assumptions.lease_treatment,
                "wacc": output.wacc.wacc,
                "cost_of_equity": output.wacc.cost_of_equity,
                "terminal_growth": output.terminal.perpetuity_growth_rate,
                "enterprise_value_gbp_m": v.enterprise_value,
                "net_debt_deducted_gbp_m": v.net_debt_deducted,
                "equity_value_gbp_m": v.equity_value,
                "implied_price_pence": v.implied_share_price_pence,
                "market_price_pence": v.market_share_price_pence,
                "upside": v.upside_downside,
                "tv_share_of_ev": v.terminal_value_share_of_ev,
            }
        ]
    )
    summary_path = out_dir / "valuation_summary.csv"
    summary.to_csv(summary_path, index=False)
    written.append(summary_path)

    return written


def export_chart(output: DcfOutput, out_dir: Path) -> Path | None:
    """Plot the value build-up. Returns None if matplotlib is unavailable."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    d = output.valuation.discounted_table
    v = output.valuation
    a = output.assumptions

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    positions = range(len(d))
    ax1.bar(positions, d["free_cash_flow"], label="Undiscounted FCF",
            color="#9ec5e8", edgecolor="#4a7fb0")
    ax1.bar(positions, d["pv_free_cash_flow"], label="Present value",
            color="#1f5d8c", width=0.5)
    ax1.set_xticks(list(positions))
    ax1.set_xticklabels(d["year"], rotation=45, ha="right")
    ax1.set_title("Unlevered free cash flow (£m)")
    ax1.legend(frameon=False)
    ax1.spines[["top", "right"]].set_visible(False)

    labels = ["PV of\nforecast FCF", "PV of\nterminal value",
              "Less: net debt,\nleases &\nminorities", "Equity\nvalue"]
    bridge_deduction = -(
        v.net_debt_deducted
        + a.equity_bridge.pension_deficit
        + a.equity_bridge.minority_interests
        - a.equity_bridge.investments
    )
    values = [v.pv_explicit_fcf, v.pv_terminal_value, bridge_deduction, v.equity_value]
    colours = ["#1f5d8c", "#4a7fb0", "#c75a5a", "#2e8b57"]
    ax2.bar(labels, values, color=colours)
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_title("Enterprise value to equity value (£m)")
    ax2.spines[["top", "right"]].set_visible(False)
    for i, val in enumerate(values):
        ax2.text(i, val, f"{val:,.0f}", ha="center",
                 va="bottom" if val >= 0 else "top", fontsize=9)

    fig.suptitle(
        f"{a.meta.get('company', 'DCF')} — implied "
        f"{v.implied_share_price_pence:,.0f}p vs market "
        f"{v.market_share_price_pence:,.0f}p ({v.upside_downside:+.1%})",
        fontsize=12,
    )
    fig.tight_layout()

    path = out_dir / "dcf_summary.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
