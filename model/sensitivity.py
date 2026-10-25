"""Discount-rate (WACC) sensitivity on a target DCF value (project P3).

Given a target's free-cash-flow profile, sweep the discount rate (WACC) from
6% to 12% to show the resulting enterprise-value range and how the implied
EV/EBITDA multiple moves as the discount rate changes.

The model is a two-stage FCF-DCF:
  * an explicit projection period (default 5 years) with a constant FCF CAGR,
  * a terminal (Gordon-growth) value after the explicit period.

Everything is analytic and runs on numpy/pandas only.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# DCF defaults (100-unit EBITDA base for easy reading)
# ---------------------------------------------------------------------------
DEFAULT_BASE_FCF = 100.0          # year-1 free cash flow (units)
DEFAULT_FCF_CAGR = 0.05          # explicit-period FCF growth (5%)
DEFAULT_PROJECTION_YEARS = 5
DEFAULT_TERMINAL_GROWTH = 0.025  # perpetual terminal growth (2.5%)
DEFAULT_WACC_RANGE = np.arange(0.06, 0.12 + 1e-9, 0.01)   # 6% .. 12% step 1%
DEFAULT_EBITDA = 100.0           # used for implied-multiple denominator


def fcf_schedule(base_fcf: float, cagr: float, years: int) -> np.ndarray:
    """Explicit-period free cash flows at a constant CAGR.

    year-1 FCF = base_fcf, growing by (1 + cagr) each subsequent year.
    """
    if base_fcf <= 0:
        raise ValueError("base_fcf must be > 0")
    t = np.arange(1, years + 1)
    return base_fcf * (1.0 + cagr) ** (t - 1)


def terminal_value(final_fcf: float, terminal_growth: float,
                   wacc: float) -> float:
    """Gordon-growth terminal value at the end of the explicit period.

    TV = FCF_final * (1 + g) / (wacc - g)

    Requires wacc > terminal_growth (a rate <= terminal growth makes the
    model blow up and is flagged by the caller).
    """
    if wacc <= terminal_growth:
        raise ValueError(
            f"wacc ({wacc:.3f}) must exceed terminal growth "
            f"({terminal_growth:.3f})")
    return final_fcf * (1.0 + terminal_growth) / (wacc - terminal_growth)


def dcf_value(
    base_fcf: float = DEFAULT_BASE_FCF,
    fcf_cagr: float = DEFAULT_FCF_CAGR,
    projection_years: int = DEFAULT_PROJECTION_YEARS,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
    wacc: float = 0.08,
) -> float:
    """Enterprise value of the target at a single discount rate.

    PV of the explicit FCFs + PV of the Gordon terminal value.
    """
    if wacc <= 0:
        raise ValueError("wacc must be > 0")
    fcfs = fcf_schedule(base_fcf, fcf_cagr, projection_years)
    pv_fcf = sum(cf / (1.0 + wacc) ** t for t, cf in enumerate(fcfs, start=1))
    tv = terminal_value(fcfs[-1], terminal_growth, wacc)
    pv_tv = tv / (1.0 + wacc) ** projection_years
    return pv_fcf + pv_tv


def implied_multiple(dcf_value_: float, ebitda: float) -> float:
    """Implied EV/EBITDA multiple from a DCF value and a base EBITDA."""
    if ebitda <= 0:
        raise ValueError("ebitda must be > 0")
    return dcf_value_ / ebitda


def wacc_sweep(
    waccs: Optional[List[float]] = None,
    base_fcf: float = DEFAULT_BASE_FCF,
    fcf_cagr: float = DEFAULT_FCF_CAGR,
    projection_years: int = DEFAULT_PROJECTION_YEARS,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
    ebitda: float = DEFAULT_EBITDA,
) -> pd.DataFrame:
    """Sweep WACC and return the DCF value + implied multiple per rate.

    Rows = discount rate. Columns:
      WACC, DCF value (EV), Implied EV/EBITDA, and the explicit vs terminal
      value split so the viewer can see how much value sits in the terminal.
    """
    waccs = (np.asarray(waccs, dtype=float) if waccs is not None
             else DEFAULT_WACC_RANGE)
    rows = []
    for w in waccs:
        if w <= terminal_growth:
            rows.append({
                "WACC": w, "DCF value": np.nan, "Implied EV/EBITDA": np.nan,
                "PV explicit": np.nan, "PV terminal": np.nan,
                "terminal % of value": np.nan,
            })
            continue
        fcfs = fcf_schedule(base_fcf, fcf_cagr, projection_years)
        pv_fcf = sum(cf / (1.0 + w) ** t for t, cf in enumerate(fcfs, start=1))
        pv_tv = terminal_value(fcfs[-1], terminal_growth, w) / (1.0 + w) ** projection_years
        value = pv_fcf + pv_tv
        rows.append({
            "WACC": w,
            "DCF value": value,
            "Implied EV/EBITDA": implied_multiple(value, ebitda),
            "PV explicit": pv_fcf,
            "PV terminal": pv_tv,
            "terminal % of value": pv_tv / value,
        })
    df = pd.DataFrame(rows).set_index("WACC")
    df.index.name = "WACC"
    return df


def value_range(
    waccs: Optional[List[float]] = None,
    base_fcf: float = DEFAULT_BASE_FCF,
    fcf_cagr: float = DEFAULT_FCF_CAGR,
    projection_years: int = DEFAULT_PROJECTION_YEARS,
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH,
) -> dict:
    """Headline DCF range (high = low WACC, low = high WACC) + value/yr-EBITDA.

    Returns a small dict the notebook/report can drop straight into a bullet.
    """
    df = wacc_sweep(waccs, base_fcf, fcf_cagr, projection_years, terminal_growth)
    valid = df["DCF value"].dropna()
    return {
        "wacc_lo": float(df.index.min()),
        "wacc_hi": float(df.index.max()),
        "value_at_low_wacc": float(valid.iloc[0]),
        "value_at_high_wacc": float(valid.iloc[-1]),
        "range_width_pct": float((valid.iloc[0] / valid.iloc[-1] - 1.0) * 100),
    }


if __name__ == "__main__":
    print("WACC sensitivity on a 100-unit EBITDA target "
          "(5yr FCF CAGR 5%, terminal 2.5%)\n")
    df = wacc_sweep()
    out = df.copy()
    out["DCF value"] = out["DCF value"].round(2)
    out["Implied EV/EBITDA"] = out["Implied EV/EBITDA"].round(2)
    out["terminal % of value"] = (out["terminal % of value"] * 100).round(1)
    print(out.to_string())
    rng = value_range()
    print(f"\nValue range: {rng['value_at_low_wacc']:.1f} -> "
          f"{rng['value_at_high_wacc']:.1f} "
          f"({rng['range_width_pct']:.0f}% wide as WACC goes 6% -> 12%)")
