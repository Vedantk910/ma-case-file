"""Pytest suite for the M&A screening case-file models.

Covers the three requirements:
  (a) accretion sign at known inputs
  (b) IRR bisection converges on a known cash-flow
  (c) sensitivity grid has the expected shape
plus a couple of supporting checks.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable so `model` and `data` resolve regardless
# of where pytest is launched from.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pytest

from model import accretive, rollup, sensitivity


# ---------------------------------------------------------------------------
# (a) Accretion sign at known inputs
# ---------------------------------------------------------------------------
def test_accretion_low_multiple_is_accretive():
    """Cheap entry (6x) with full synergy capture should lift year-1 EPS."""
    val = accretive.accretion(multiple=6.0, synergy_capture=1.0)
    assert val > 0, f"expected accretion>0, got {val}"


def test_accretion_high_multiple_is_dilutive():
    """Expensive entry (12x) with no synergy capture should dilute year-1 EPS."""
    val = accretive.accretion(multiple=12.0, synergy_capture=0.0)
    assert val < 0, f"expected dilution<0, got {val}"


def test_accretion_monotone_in_multiple():
    """More expensive entry must never be more accretive, at fixed capture."""
    row = [accretive.accretion(multiple=m, synergy_capture=0.5)
           for m in (6.0, 9.0, 12.0)]
    assert row[0] > row[1] > row[2], f"not monotone-decreasing: {row}"


# ---------------------------------------------------------------------------
# (b) IRR bisection converges on a known cash-flow
# ---------------------------------------------------------------------------
def test_irr_bisection_single_period_known():
    """-1000 then +1100 has a closed-form IRR of exactly 10%."""
    r = rollup.irr_bisection([-1000.0, 1100.0])
    assert r is not None
    assert abs(r - 0.10) < 1e-4, f"IRR {r} != 10%"


def test_irr_bisection_zero_growth_flat_multiple_is_loss():
    """Buy at 8x, EBITDA flat, exit at 6x with 4x leverage -> negative IRR.

    Equity at entry = 8-4 = 4; exit value = 6-4 = 2; half of equity back over
    5 years is deeply negative.
    """
    r = rollup.deal_irr(entry_multiple=8.0, exit_multiple=6.0,
                        leverage=4.0, ebitda_cagr=0.0, hold_years=5)
    assert r is not None and r < 0, f"expected negative IRR, got {r}"


def test_irr_bisection_matches_np_check():
    """The IRR returned must zero the NPV (residual check)."""
    cfs = rollup.sponsor_cash_flows(
        ebitda_entry=100.0, entry_multiple=8.0, exit_multiple=10.0,
        leverage=4.0, hold_years=5, ebitda_cagr=0.04)
    r = rollup.irr_bisection(cfs)
    assert r is not None
    resid = rollup.npv(r, cfs)
    assert abs(resid) < 1e-3, f"NPV residual too large: {resid}"


# ---------------------------------------------------------------------------
# (c) Sensitivity grid has the expected shape
# ---------------------------------------------------------------------------
def test_sensitivity_grid_shape():
    """WACC sweep from 6%..12% step 1% must give 7 rows and the right cols."""
    df = sensitivity.wacc_sweep()
    assert df.shape[0] == 7, f"expected 7 WACC rows, got {df.shape[0]}"
    for col in ("DCF value", "Implied EV/EBITDA", "terminal % of value"):
        assert col in df.columns, f"missing column {col}"


def test_sensitivity_value_decreasing_in_wacc():
    """Higher discount rate must give a lower DCF value."""
    df = sensitivity.wacc_sweep()
    vals = df["DCF value"].to_numpy()
    assert np.all(np.diff(vals) < 0), f"DCF not decreasing in WACC: {vals}"


# ---------------------------------------------------------------------------
# Roll-up matrix shape (supporting)
# ---------------------------------------------------------------------------
def test_rollup_matrix_shape():
    df = rollup.rollup_irr_matrix()
    assert df.shape == (7, 7), f"expected 7x7 IRR grid, got {df.shape}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
