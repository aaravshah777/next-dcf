# NEXT plc — Discounted Cash Flow Model

[![CI](https://github.com/aaravshah777/supreme-guacamole/actions/workflows/ci.yml/badge.svg)](https://github.com/aaravshah777/supreme-guacamole/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

A transparent, fully tested DCF valuation of **NEXT plc (LSE: NXT)** in Python.
Everything is in sterling, every assumption lives in a single YAML file, and the
IFRS 16 lease problem is handled explicitly rather than swept under the carpet.

> **Replace `YOUR-USERNAME` in the badge URL above with your GitHub username once you push.**

---

## Headline result

| | |
|---|---|
| WACC | **9.90%** |
| Enterprise value | **£16.6bn** |
| Equity value | **£13.8bn** |
| Implied value per share | **11,525p (£115.25)** |
| Market price (early Oct 2026) | 14,210p (£142.10) |
| Implied upside | **−18.9%** |
| Terminal value as % of EV | 70.3% |
| Sensitivity range | 8,380p to 17,857p |

**The base case says Next is overvalued.** Before accepting that, note what is
driving it: the 10-year gilt is around 5.5%, close to its highest since 2008,
which pushes the cost of equity to 10.73% and the WACC to 9.90%. A DCF is a
statement about the discount rate as much as about the company, and right now
the discount rate is doing most of the talking.

Reverse-engineering the market price makes this concrete. The valuation reaches
14,210p at a **WACC of 8.69%** (1.21pp below the base case), which corresponds
to a gilt yield of about **4.1%** rather than today's 5.48%. Alternatively it
reaches the market price at **4.01% perpetuity growth** — above the long-run
growth rate of the UK economy, and therefore not credible.

So the honest reading is not "the market is wrong" but "the market is pricing a
long-run risk-free rate well below today's gilt curve." Whether that is
reasonable is a macro judgement, and it is the real question this valuation
raises.

---

## Quick start

```bash
git clone https://github.com/aaravshah777/supreme-guacamole.git
cd next-dcf

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

python run_dcf.py                # full model, printed to the terminal
```

Other ways to run it:

```bash
python run_dcf.py --export                      # write CSVs and a chart to outputs/
python run_dcf.py --wacc 0.084                  # override the discount rate
python run_dcf.py --terminal-growth 0.020       # override perpetuity growth
python run_dcf.py --lease-treatment expensed    # the pre-IFRS 16 view
python run_dcf.py --no-sensitivity              # skip the grids
pytest -v                                       # run the 79-test suite
```

---

## The five steps

### Step 1 — Forecast free cash flow (`dcf/forecast.py`)

We discount **free cash flow to the firm (FCFF)**, also called unlevered free
cash flow: cash generated before any payment to lenders or shareholders. It has
to be unlevered because we discount at the WACC, which already contains the cost
of debt. Discounting a cash flow that is net of interest at the WACC
double-counts the cost of debt.

```
  Revenue                          grown at the forecast growth rate
× Operating margin
= EBIT
× (1 − effective tax rate)
= NOPAT
+ Depreciation & amortisation      non-cash, added back (see lease note)
− Capital expenditure              cash out, never hits the P&L directly
− Increase in net working capital  cash tied up in the balance sheet
= Unlevered free cash flow
```

Three choices worth defending in a write-up:

**The 53rd week.** FY2026 was a 53-week year, roughly 2% longer than normal.
FY2027 growth is held at 4.0% to absorb the unwind. Forecasting off the inflated
base without this adjustment compounds the error through every year.

**Working capital consumes cash.** Next lends to its own customers through Next
Finance, and that credit book (£1,583m, about 23% of revenue) sits in
receivables. Net working capital is therefore strongly *positive*, so growth
ties up cash. This is the opposite of a supermarket or an FMCG group, where
suppliers are paid after customers pay and growth releases cash. Carrying the
wrong intuition across is a real error, not a presentational one.

**Capex is far below depreciation.** £135m against £325m. That is not a company
under-investing; it is IFRS 16, and it leads directly to the next point.

### The IFRS 16 lease problem

Next leases nearly all of its c.450 stores. Under IFRS 16 those leases sit on
the balance sheet as a liability with a matching right-of-use asset, and the
rent charge is split into depreciation and interest. There are two internally
consistent ways to handle this, and **mixing them inflates the valuation badly**:

| | `capitalised` (IFRS 16) | `expensed` (pre-IFRS 16) |
|---|---|---|
| EBIT measured after | right-of-use depreciation | full cash rent |
| D&A added back | all of it | non-lease portion only |
| Lease liabilities | deducted as debt | not deducted |
| Implied price | **11,525p** | **9,553p** |

The trap is adding back right-of-use depreciation (which flatters cash flow)
while ignoring the lease liability (which would reduce equity value). That takes
the benefit of the lease and none of the cost, and on Next it is worth well over
£1bn of phantom value. The model derives both the D&A add-back and the net debt
deduction from one `lease_treatment` setting so they cannot drift apart, and
`tests/test_leases.py` enforces it.

**Why the two columns don't agree.** The gap is about 17%, and it is genuine
rather than a bug. The pre-IFRS 16 view charges rent in perpetuity, because a
going-concern retailer keeps paying rent forever. The IFRS 16 liability only
captures *committed* lease terms, implicitly assuming leases end and are not
renewed. Neither is quite right: the true economic obligation sits between them.
Treat the two numbers as a range and say so, rather than forcing the inputs to
make them agree.

### Step 2 — Weighted average cost of capital (`dcf/wacc.py`)

```
WACC = E/(D+E) × Ke + D/(D+E) × Kd × (1 − t)
Ke   = Rf + β × ERP
```

| Input | Value | Reasoning |
|---|---|---|
| Risk-free rate | 5.48% | 10-year gilt — see the note below |
| Equity risk premium | 5.00% | UK mature-market ERP |
| Levered beta | 1.05 | Discretionary clothing retail is cyclical |
| **Cost of equity** | **10.73%** | |
| Pre-tax cost of debt | 6.30% | Gilt + c.80bp; Next is investment grade |
| After-tax cost of debt | 4.73% | Interest is tax-deductible at 25% |
| Weights (E/D) | 86.1% / 13.9% | At **market** value, not book |
| **WACC** | **9.90%** | |

**On the gilt yield.** At 5.48% it is near a 2008 high, and it feeds straight
into the cost of equity. Resist the temptation to "correct" it towards the
textbook 8% WACC — the point of CAPM is that the discount rate moves with the
market. But do say in your write-up that the valuation is unusually sensitive to
this single input today, and show the sensitivity table to prove you know it.

**Market-value weights matter here.** Next's book equity is about £1.8bn against
a £17bn market capitalisation. Using book weights would put debt at roughly 60%
of capital instead of 14%, and the WACC would be meaningfully wrong.

### Step 3 — Terminal value (`dcf/terminal.py`)

```
Gordon Growth:   TV = FCF_n × (1 + g) / (WACC − g)
Exit multiple:   TV = EBITDA_n × multiple
```

The `(1 + g)` matters: the perpetuity formula values a stream that *starts* one
period after the valuation point. Omitting it is the most common slip in the
whole model.

We use **2.5%** perpetuity growth — modestly above the 2% inflation target to
allow for some real growth, and comfortably below the WACC.

The model computes **both** methods every run and prints two cross-checks:

- The exit EV/EBITDA implied by the growth rate: **9.6x**, against the 8.0x
  assumption drawn from where UK retail trades. The Gordon Growth case is
  therefore the more generous of the two.
- The perpetuity growth implied by an 8.0x exit: **1.15%**.

A warning specific to lease-heavy retailers: post-IFRS 16 EBITDA is *larger*
than the pre-IFRS 16 figure, because rent has moved out of operating costs. If
you take an exit multiple from peers quoted on a pre-IFRS 16 basis and apply it
to post-IFRS 16 EBITDA, you will overstate the terminal value substantially.

### Step 4 — Discount the cash flows (`dcf/valuation.py`)

```
PV = CF_t / (1 + WACC)^t
```

Mid-year convention is on by default: cash arrives through the year, so flows
are discounted at `t − 0.5`, lifting the valuation by about `(1 + WACC)^0.5`.
The terminal value is discounted at `t = n`, **not** `n + 1` — it is already
measured as at the end of the final forecast year.

### Step 5 — Implied share price (`dcf/valuation.py`)

```
  Enterprise value              £16,618m
− Net debt excluding leases      −1,714m
− Lease liabilities (IFRS 16)    −1,030m
− Minority interests               −118m
+ Investments                       +35m
= Equity value                  £13,791m
÷ Shares outstanding             119.66m
= £115.25 per share  →  11,525p
```

**On deducting Next's net debt in full.** Most of Next's borrowing funds the
Next Finance receivables book rather than the retail operation. We still deduct
all of it, because the interest income those receivables earn is already inside
forecast revenue. The alternative is to carve out the credit business and value
it separately — more rigorous, considerably more work, and you must not do half
of each. Deducting the debt while excluding the interest income would
double-count the cost of the credit book.

---

## Sensitivity analysis

**WACC vs terminal growth** (implied price in pence)

|  | g = 1.50% | g = 2.00% | g = 2.50% | g = 3.00% | g = 3.50% |
|---|---|---|---|---|---|
| **WACC 8.40%** | 13,008 | 13,936 | 15,022 | 16,308 | 17,857 |
| **WACC 9.15%** | 11,508 | 12,237 | 13,075 | 14,050 | 15,197 |
| **WACC 9.90%** | 10,277 | 10,862 | **11,525** | 12,285 | 13,163 |
| **WACC 10.65%** | 9,250 | 9,727 | 10,262 | 10,868 | 11,558 |
| **WACC 11.40%** | 8,380 | 8,775 | 9,214 | 9,705 | 10,259 |

The market price of 14,210p sits in the top-left region — reachable at a WACC
around 8.4% with 2.5% growth, or at 9.15% with growth above 3%. A second grid
flexes the operating margin, and a third compares the two lease treatments.

Note how much more the valuation moves on the discount rate than on the
operating margin. That is the structural weakness of any DCF of a mature
business: **the answer is mostly a statement about the terminal assumptions**,
not about the next five years of trading. Saying so reads as judgement, not
hedging.

---

## Project structure

```
next-dcf/
├── assumptions.yaml            every input, with sourcing comments
├── run_dcf.py                  command-line entry point
├── dcf/
│   ├── __init__.py             public API
│   ├── inputs.py               typed assumption containers + YAML loader
│   ├── forecast.py             STEP 1 — free cash flow forecast
│   ├── wacc.py                 STEP 2 — cost of capital
│   ├── terminal.py             STEP 3 — terminal value
│   ├── valuation.py            STEPS 4 & 5 — discounting and equity bridge
│   ├── model.py                orchestration, owns the lease-treatment choice
│   ├── sensitivity.py          sensitivity grids + lease comparison
│   └── report.py               console output, CSV and chart export
├── tests/                      79 tests, including a file for the lease logic
├── .github/workflows/ci.yml    runs tests + the model on every push
└── outputs/                    generated CSVs and chart (git-ignored)
```

Import any single step on its own:

```python
from dcf import load_assumptions, run_dcf, gordon_growth_terminal_value

output = run_dcf(load_assumptions("assumptions.yaml"))
print(f"{output.wacc.wacc:.2%}")
print(f"{output.valuation.implied_share_price_pence:,.0f}p")

# Or use a single formula in isolation, e.g. for a tutorial question
print(gordon_growth_terminal_value(final_year_fcf=1352, wacc=0.099, growth=0.025))
```

---

## Source data

Base year is the **53 weeks ended 31 January 2026 (FY2026)**, reported 26 March
2026. All figures in GBP.

| Item | Value | Source |
|---|---|---|
| Revenue (incl. credit interest) | £6,901m | FY2026 results |
| Operating profit | £1,276m (18.50%) | FY2026 results |
| Profit before tax | £1,190m | FY2026 results |
| Depreciation & amortisation | £325.3m | Cash flow statement |
| Capital expenditure | £135.4m | Cash flow statement |
| Free cash flow | £1,098m | Cash flow statement |
| Net debt excluding leases | £1,714m | Balance sheet, 31 Jan 2026 |
| Customer receivables | £1,583m | Balance sheet |
| Minority interests | £118m | Balance sheet |
| Shares outstanding | 119.66m | Total voting rights, 29 May 2026 |
| Share price | 14,210p | NXT.L, early October 2026 |
| 10-year gilt | 5.48% | Early October 2026 |

### Figures to verify before you submit

Three inputs are estimates rather than figures read off the accounts. Replace
them and the model is fully sourced:

1. **Lease liabilities, £1,030m.** Built from the long-term figure plus an
   estimated current portion. Take the real total from the lease note.
2. **Right-of-use depreciation, 2.5% of revenue.** Needed for the `expensed`
   comparison. Take it from the property, plant and equipment note.
3. **Cash rent, 3.0% of revenue.** Take the lease payment line from the cash
   flow statement.

Also update the share price, gilt yield and share count before each use — Next
buys back shares aggressively (£721.9m in FY2026), so the count falls steadily.

---

## Known limitations

Worth stating explicitly in any write-up. Examiners reward knowing where your
model is weak far more than they reward a tidy number.

1. **Terminal value is 70% of EV.** The explicit five-year forecast matters
   less than the perpetuity assumptions. A 10-year horizon would reduce this.
2. **The credit book is not valued separately.** Next Finance is a lending
   business inside a retailer, with different economics and different risk. A
   sum-of-the-parts treating it as a financial subsidiary would be more
   rigorous.
3. **One discount rate for two businesses.** Related to the above: retail and
   consumer lending do not deserve the same WACC.
4. **The gilt yield is at a multi-decade high.** The valuation is unusually
   sensitive to a rate that may not persist. Consider a normalised risk-free
   rate as a second case.
5. **Beta is assumed, not estimated.** 1.05 is reasonable for cyclical retail,
   but regressing five years of weekly returns against the FTSE All-Share
   yourself would be a genuine improvement and an easy extension.
6. **No explicit balance sheet.** Working capital is a percentage of revenue
   rather than modelled from receivables, inventory and payables individually.
7. **Buybacks are ignored in the forecast.** Next returns most of its free cash
   flow through buybacks, so the share count will keep falling. This affects
   value per share even when it does not affect enterprise value.
8. **Overseas growth is not modelled separately.** Next's international and
   Total Platform businesses grow faster but at lower margins than UK retail;
   a segmented forecast would capture the mix shift.

---

## Suggested extensions

- Estimate beta yourself from price history rather than assuming it.
- Add bull / base / bear YAML files and run all three (`--assumptions bear.yaml`).
- Build a sum-of-the-parts that values Next Finance separately from retail.
- Add a comparable-companies multiples valuation (M&S, JD Sports, Inditex,
  H&M, Frasers) and triangulate against the DCF.
- Run a Monte Carlo over WACC, growth and margin and plot the distribution of
  implied prices rather than a point estimate.

---

## Disclaimer

Built as an educational exercise for a BSc Finance degree. Not investment
advice, not a recommendation to buy or sell any security, and not a substitute
for professional financial advice. Figures are drawn from public sources and may
contain errors; verify anything you rely on against the primary filings.

## Licence

MIT — see [LICENSE](LICENSE).
