"""LBO-lite roll-up IRR matrix (project P3).

A private-equity-style roll-up screen: buy a target at an entry multiple,
leverage it, let EBITDA grow at a stated CAGR for a fixed hold, and exit at
a chosen multiple. Output is the sponsor IRR. The matrix sweeps entry x exit
multiples (6x..12x) at a stated leverage, 5-year hold.

IRR is solved by bisection on NPV(r) = 0 (numpy_financial is NOT used, so
no extra dependency is required).

Cash-flow model (year 0 = entry, years 1..H = hold):
  - EV = EBITDA_entry * multiple
  - Debt = leverage * EBITDA_entry        (leverage in "x EBITDA")
  - Equity = EV - Debt
  - Interest is NOT modelled explicitly (LBO-lite): we let EBITDA grow and
    assume net income to sponsor = EBITDA (1 - no cash-out) plus whatever the
    equity is worth at exit. This keeps the screen analytic; see the
    docstring caveats.
  - Exit EV = EBITDA_exit * exit_multiple, EBITDA_exit = EBITDA_entry*(1+g)^H
  - Sponsor cash at exit = Exit EV - Debt (debt held flat)
  - IRR solves: -Equity + Sponsor_cash_at_exit / (1 + IRR)^H = 0
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_MULTIPLES = np.arange(6.0, 12.0 + 1e-9, 1.0)   # 6..12
DEFAULT_LEVERAGE = np.array([3.0, 4.0, 5.0])          # x EBITDA
DEFAULT_HOLD_YEARS = 5
DEFAULT_EBITDA_CAGR = 0.04                             # 4% EBITDA growth
DEFAULT_EBITDA_ENTRY = 100.0                           # 100-unit base

# Bisection bracket: IRR of a levered 5-yr deal comfortably lives in here.
IRR_LO = -0.99     # -99%  (near-total loss)
IRR_HI = 5.0      # +500%  (upper bound)
IRR_TOL = 1e-7
IRR_MAX_ITER = 300


# ---------------------------------------------------------------------------
# IRR by bisection (numpy_financial not required)
# ---------------------------------------------------------------------------
def npv(rate: float, cash_flows: List[float]) -> float:
    """Net present value of a cash-flow series at a given discount rate.

    cash_flows[0] is at time 0 (not discounted).
    """
    cf = np.asarray(cash_flows, dtype=float)
    t = np.arange(cf.size)
    return float(np.sum(cf / (1.0 + rate) ** t))


def irr_bisection(
    cash_flows: List[float],
    lo: float = IRR_LO,
    hi: float = IRR_HI,
    tol: float = IRR_TOL,
    max_iter: int = IRR_MAX_ITER,
) -> Optional[float]:
    """Solve NPV(r) = 0 by bisection; return the rate or None if no sign change.

    Bisection is robust for a single-crossing IRR (our levered-deal case) and
    needs no external library. Returns None if the bracket never straddles a
    root (e.g. all-negative or all-positive flows).
    """
    cf = list(cash_flows)
    if cf[0] == 0.0 and all(c == 0.0 for c in cf):
        raise ValueError("all-zero cash flows have no IRR")

    f_lo = npv(lo, cf)
    f_hi = npv(hi, cf)

    # If both ends have the same sign, try to expand the bracket so a sign
    # change is captured (handles deeply negative or very positive IRRs).
    if f_lo * f_hi > 0:
        return None

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = npv(mid, cf)
        if abs(f_mid) < tol or (hi - lo) < tol:
            return mid
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo = mid
            f_lo = f_mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Deal-level IRR
# ---------------------------------------------------------------------------
def sponsor_cash_flows(
    ebitda_entry: float = DEFAULT_EBITDA_ENTRY,
    entry_multiple: float = 8.0,
    exit_multiple: float = 10.0,
    leverage: float = DEFAULT_LEVERAGE[1],
    hold_years: int = DEFAULT_HOLD_YEARS,
    ebitda_cagr: float = DEFAULT_EBITDA_CAGR,
) -> List[float]:
    """Sponsor cash flows: [ -equity, 0, ..., 0, +exit_equity_value ].

    Equity at entry = EV - Debt. Sponsor value at exit = Exit EV - Debt.
    Years 1..H-1 are zero (no intermediate cash-out in this LBO-lite screen).
    """
    ev_entry = ebitda_entry * entry_multiple
    debt = leverage * ebitda_entry
    equity = ev_entry - debt
    ebitda_exit = ebitda_entry * (1.0 + ebitda_cagr) ** hold_years
    ev_exit = ebitda_exit * exit_multiple
    exit_value = ev_exit - debt

    cfs = [equity] + [0.0] * (hold_years - 1) + [exit_value]
    # flip entry to outflow
    cfs[0] = -equity
    return cfs


def deal_irr(
    ebitda_entry: float = DEFAULT_EBITDA_ENTRY,
    entry_multiple: float = 8.0,
    exit_multiple: float = 10.0,
    leverage: float = DEFAULT_LEVERAGE[1],
    hold_years: int = DEFAULT_HOLD_YEARS,
    ebitda_cagr: float = DEFAULT_EBITDA_CAGR,
) -> Optional[float]:
    """Sponsor IRR for a single roll-up deal (0.10 = 10%)."""
    cfs = sponsor_cash_flows(ebitda_entry, entry_multiple, exit_multiple,
                             leverage, hold_years, ebitda_cagr)
    return irr_bisection(cfs)


def deal_equity_multiple(
    ebitda_entry: float = DEFAULT_EBITDA_ENTRY,
    entry_multiple: float = 8.0,
    exit_multiple: float = 10.0,
    leverage: float = DEFAULT_LEVERAGE[1],
    hold_years: int = DEFAULT_HOLD_YEARS,
    ebitda_cagr: float = DEFAULT_EBITDA_CAGR,
) -> float:
    """Equity multiple (MOC) at exit: exit value / entry equity."""
    cfs = sponsor_cash_flows(ebitda_entry, entry_multiple, exit_multiple,
                             leverage, hold_years, ebitda_cagr)
    entry_equity = -cfs[0]
    exit_value = cfs[-1]
    return exit_value / entry_equity


def rollup_irr_matrix(
    multiples: Optional[List[float]] = None,
    leverage: float = DEFAULT_LEVERAGE[1],
    hold_years: int = DEFAULT_HOLD_YEARS,
    ebitda_cagr: float = DEFAULT_EBITDA_CAGR,
    ebitda_entry: float = DEFAULT_EBITDA_ENTRY,
) -> pd.DataFrame:
    """IRR matrix: rows = entry multiple, columns = exit multiple.

    All cells are sponsor IRRs (%) for the stated leverage and hold.
    A cell where entry > exit can still be positive because EBITDA grows;
    the matrix surfaces exactly that.
    """
    multiples = (np.asarray(multiples, dtype=float) if multiples is not None
                 else DEFAULT_MULTIPLES)
    grid = np.full((len(multiples), len(multiples)), np.nan)
    for i, entry in enumerate(multiples):
        for j, exit_ in enumerate(multiples):
            r = deal_irr(ebitda_entry, entry, exit_, leverage,
                         hold_years, ebitda_cagr)
            grid[i, j] = (r * 100.0) if r is not None else np.nan

    cols = [f"{int(m)}x" for m in multiples]
    df = pd.DataFrame(
        grid,
        index=[f"{int(m)}x" for m in multiples],
        columns=cols,
    )
    df.index.name = "Entry EV/EBITDA"
    df.columns.name = (
        f"Exit EV/EBITDA (lev {leverage:.0f}x, {hold_years}yr, "
        f"{ebitda_cagr*100:.0f}% CAGR)"
    )
    return df


if __name__ == "__main__":
    for lev in DEFAULT_LEVERAGE:
        print(f"Sponsor IRR matrix @ leverage {lev:.0f}x EBITDA, "
              f"{DEFAULT_HOLD_YEARS}yr hold, {DEFAULT_EBITDA_CAGR*100:.0f}% "
              f"EBITDA CAGR\n")
        print(rollup_irr_matrix(leverage=lev).round(1).to_string())
        print()
