#!/usr/bin/env python3
"""Command-line entry point for the NEXT plc DCF model.

    python run_dcf.py                          # base case, printed to the terminal
    python run_dcf.py --export                 # also write CSVs and a chart
    python run_dcf.py --wacc 0.090             # override the WACC directly
    python run_dcf.py --terminal-growth 0.020  # override terminal growth
    python run_dcf.py --lease-treatment expensed   # pre-IFRS 16 view
    python run_dcf.py --assumptions bear.yaml  # run a different scenario file
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from dcf import (
    lease_treatment_comparison,
    load_assumptions,
    run_dcf,
    wacc_vs_growth,
    wacc_vs_margin,
)
from dcf.report import export_chart, export_csv, print_report
from dcf.sensitivity import summary_statistics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Five-step DCF valuation of NEXT plc.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--assumptions",
        default="assumptions.yaml",
        help="Path to the assumptions file (default: assumptions.yaml).",
    )
    parser.add_argument(
        "--wacc",
        type=float,
        default=None,
        help="Override the computed WACC with this decimal rate, e.g. 0.090.",
    )
    parser.add_argument(
        "--terminal-growth",
        type=float,
        default=None,
        help="Override the perpetuity growth rate, e.g. 0.020.",
    )
    parser.add_argument(
        "--lease-treatment",
        choices=["capitalised", "expensed"],
        default=None,
        help="Override the lease treatment (default: whatever the YAML says).",
    )
    parser.add_argument(
        "--no-sensitivity",
        action="store_true",
        help="Skip the sensitivity tables (faster).",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Write CSV outputs and a summary chart to --out-dir.",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs",
        help="Directory for exported files (default: outputs).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        assumptions = load_assumptions(args.assumptions)
    except (FileNotFoundError, KeyError, ValueError, TypeError) as exc:
        print(f"Could not load assumptions: {exc}", file=sys.stderr)
        return 1

    if args.lease_treatment:
        assumptions = dataclasses.replace(
            assumptions, lease_treatment=args.lease_treatment
        )

    # Command-line overrides are expressed as deltas against the base case, so
    # the rest of the model needs no special handling.
    wacc_delta = 0.0
    growth_delta = 0.0
    if args.wacc is not None:
        base_wacc = run_dcf(assumptions).wacc.wacc
        wacc_delta = args.wacc - base_wacc
    if args.terminal_growth is not None:
        growth_delta = (
            args.terminal_growth - assumptions.terminal_value.perpetuity_growth_rate
        )

    try:
        output = run_dcf(
            assumptions, wacc_delta=wacc_delta, terminal_growth_delta=growth_delta
        )
    except ValueError as exc:
        print(f"The model could not be solved: {exc}", file=sys.stderr)
        return 1

    sensitivities = {}
    if not args.no_sensitivity:
        sensitivities = {
            "WACC vs terminal growth rate (pence per share)": wacc_vs_growth(assumptions),
            "WACC vs operating margin, parallel shift (pence per share)": (
                wacc_vs_margin(assumptions)
            ),
            "Lease treatment comparison (GBP m unless stated)": (
                lease_treatment_comparison(assumptions)
            ),
        }

    print_report(output, sensitivities or None)

    if sensitivities:
        price_grids = [
            table for title, table in sensitivities.items() if "lease" not in title.lower()
        ]
        stats = summary_statistics(price_grids)
        print(
            f"  Across every sensitivity case the implied price ranges from "
            f"{stats['min']:,.0f}p to {stats['max']:,.0f}p "
            f"(median {stats['median']:,.0f}p).\n"
        )

    if args.export:
        out_dir = Path(args.out_dir)
        written = export_csv(output, sensitivities, out_dir)
        chart = export_chart(output, out_dir)
        if chart:
            written.append(chart)
        print("  Written:")
        for path in written:
            print(f"    {path}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
