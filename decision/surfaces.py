"""The decision surface: entry multiple x synergy capture x discount rate.

The case file's ``accretion_grid`` is a 2-D slice of this: it fixes the
capture, sweeps the multiple, and reports a point.  A *decision* surface
answers the committee question - "is this specific deal worth buying at this
specific price, with this specific synergy commitment, under this cost of
capital?" - in one lookup.  Three layers:

1.  ``surface3d`` - the 3-D volume over (capture, wacc, deal price).  The
    wacc axis enters through the *intrinsic* multiple (the DCF value of the
    target's own cash flows, from ``model.sensitivity``): a deal is only in
    the "buy zone" if it is accretive AND priced below the WACC-implied
    value.  The wacc that flips a deal out of the zone is itself a
    decision boundary, not a footnote.

2.  ``zero_line`` - the accretion boundary: for each capture rate, the exact
    entry multiple at which year-1 accretion is exactly zero.  Because the
    accretion model is linear in the entry multiple (financing cost scales
    with EV, everything else is fixed at a given capture), the boundary has
    a closed form:

        m*(c) = (E*conv + S*c) / (ds * rate * E)         [EV/EBITDA units]

    with conv = target NI / target EBITDA (the net-income conversion).  The
    numerical solver in tests pins it to 1e-9.  The boundary rises with
    capture: synergies you can actually contract for buy you a wider zone.

3.  ``buy_zone`` / ``deal_trigger`` - the one-page exhibit.  ``buy_zone``
    is the 2-D (capture, wacc) boundary for a deal priced at a given
    multiple; ``deal_trigger`` collapses it to the single number a mandate
    quotes: the *minimum capture* that puts the deal in the zone under the
    committee's rate.  "Buy at >= 50% capture, else partner or build" is
    what this page separates a decision tool from a case file.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from model import accretive, sensitivity

# Sweep grids.  The wacc grid is the committee's policy band - not a free
# parameter: it is the input the client sets (Gate 5, discount-rate
# policy), and the surface just evaluates the volume over it.
DEFAULT_MULT_GRID = np.arange(6.0, 13.0 + 1e-9, 1.0)
DEFAULT_CAP_GRID = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
DEFAULT_WACC_GRID = np.arange(0.06, 0.12 + 1e-9, 0.02)


def _annuity_pv(wacc: float, years: int) -> float:
    """PV factor for a level `years`-yr annuity of $1 at `wacc`.

    Level annuity (not the decaying synergy ramp - that lives in
    ``synergy_decay``): used for the partner rate-card and cost-proxy PVs.
    """
    if wacc <= 0:
        return float(years)
    return (1.0 - (1.0 + wacc) ** -years) / wacc


def intrinsic_multiple(wacc: float,
                       base_fcf: float = sensitivity.DEFAULT_BASE_FCF,
                       ebitda: float = sensitivity.DEFAULT_EBITDA,
                       **dcf_kw) -> float:
    """The DCF-implied EV/EBITDA at a given WACC (the target's own value).

    From ``model.sensitivity`` with the case file's defaults (100-unit base
    FCF = the EBITDA base, 5% FCF CAGR, 2.5% terminal): the intrinsic
    multiple is ~31x at 6%, ~11x at 12% - the value band a deal price can
    sit inside or outside of.  A price below the intrinsic multiple is
    "cheap" for the committee's cost of capital; above it is a strategic
    premium the screen has to accept consciously.
    """
    return sensitivity.dcf_value(wacc=wacc, base_fcf=base_fcf, **dcf_kw) / ebitda


def _m_star(capture: float, kw: dict) -> float:
    """Closed-form zero-line for one capture rate (see module docstring)."""
    tgt_e = kw.get("target_ebitda", accretive.DEFAULT_TARGET_EBITDA)
    ni = kw.get("ni_per_ebitda", accretive.DEFAULT_TARGET_NI_PER_EBITDA)
    s = kw.get("annual_synergy", accretive.DEFAULT_ANNUAL_SYNERGY)
    ds = kw.get("debt_share", accretive.DEFAULT_DEBT_SHARE_OF_FUNDING)
    rate = kw.get("debt_rate", accretive.DEFAULT_DEBT_RATE)
    conv = ni + s * capture / tgt_e      # total NI per unit EBITDA at this capture
    return conv / (ds * rate)


def zero_line(
    captures: Optional[List[float]] = None,
    **accretive_kw,
) -> pd.Series:
    """The accretion zero-line: entry multiple at which year-1 accretion = 0.

    Closed form (``_m_star``), verified against
    ``model.accretive.accretion`` in the test suite: a capture of 0 gives
    the no-synergy boundary, full capture the widest zone.  ``_``-prefixed
    kwargs are for the accretion model only.
    """
    caps = (np.asarray(captures, dtype=float)
            if captures is not None else DEFAULT_CAP_GRID)
    vals = [_m_star(float(c), accretive_kw) for c in caps]
    return pd.Series(vals, index=[f"{int(c * 100)}%" for c in caps],
                     name="zero_line_multiple")


def surface3d(
    deal_price_multiple: float = 8.0,
    captures: Optional[List[float]] = None,
    waccs: Optional[List[float]] = None,
    **accretive_kw,
) -> Dict[str, object]:
    """The 3-D decision volume over (capture, wacc, deal price).

    For each wacc the buy zone at a given deal price is the set of capture
    rates where the deal is BOTH accretive at the price AND priced below
    the wacc-implied intrinsic value.  Returns the boundary surfaces plus
    the volume itself so a note can quote how many of the cells the
    committee's own rate leaves in the zone - the number that says how
    forgiving the screen is before a single deal is even priced.
    """
    caps = (np.asarray(captures, dtype=float)
            if captures is not None else DEFAULT_CAP_GRID)
    ws = (np.asarray(waccs, dtype=float)
          if waccs is not None else DEFAULT_WACC_GRID)

    intrinsic = {float(w): intrinsic_multiple(float(w)) for w in ws}
    vol: Dict[str, Dict[str, dict]] = {}
    n_cells = 0
    n_zone = 0
    for w in ws:
        row: Dict[str, dict] = {}
        intr = intrinsic[float(w)]
        for c in caps:
            cf = float(c)
            acc_ok = accretive.accretion(
                multiple=deal_price_multiple, synergy_capture=cf,
                **accretive_kw) > 0.0
            below = deal_price_multiple < intr
            in_zone = bool(acc_ok and below)
            n_cells += 1
            n_zone += int(in_zone)
            row[f"{int(c * 100)}%"] = {
                "zero_line_multiple": round(_m_star(cf, accretive_kw), 4),
                "intrinsic_multiple_at_wacc": round(intr, 4),
                "price_is_accretive": bool(acc_ok),
                "price_below_intrinsic": bool(below),
                "in_buy_zone": in_zone,
            }
        vol[f"{w * 100:.0f}%"] = row
    return {
        "deal_price_multiple": deal_price_multiple,
        "waccs": [float(w) for w in ws],
        "captures": [float(c) for c in caps],
        "intrinsic": {f"{w * 100:.0f}%": round(intrinsic[float(w)], 4)
                      for w in ws},
        "zero_line": zero_line([float(c) for c in caps], **accretive_kw).to_dict(),
        "volume": vol,
        "buy_zone_cells": n_zone,
        "total_cells": n_cells,
    }


def buy_zone(
    deal_price_multiple: float = 8.0,
    captures: Optional[List[float]] = None,
    waccs: Optional[List[float]] = None,
    **accretive_kw,
) -> pd.DataFrame:
    """The one-page boundary: for a deal priced at `deal_price_multiple`,
    which (capture, wacc) pairs put it in the buy zone?

    Rows = capture, columns = wacc, cells True/False.  The 2-D shape is the
    decision: at 8x, a 0.25 row at 8% is out (not accretive enough to
    clear the intrinsic bar at that rate) while the 0.50 row is in - the
    exact "buy at >= 50% capture" trigger a committee can put on a mandate.
    """
    caps = (np.asarray(captures, dtype=float)
            if captures is not None else DEFAULT_CAP_GRID)
    ws = (np.asarray(waccs, dtype=float)
          if waccs is not None else DEFAULT_WACC_GRID)
    intrinsic = {float(w): intrinsic_multiple(float(w)) for w in ws}

    grid = np.zeros((len(caps), len(ws)), dtype=bool)
    for i, c in enumerate(caps):
        acc_ok = accretive.accretion(multiple=deal_price_multiple,
                                     synergy_capture=float(c),
                                     **accretive_kw) > 0.0
        for j, w in enumerate(ws):
            grid[i, j] = bool(acc_ok and
                              deal_price_multiple < intrinsic[float(w)])
    df = pd.DataFrame(
        grid,
        index=[f"{int(c * 100)}% capture" for c in caps],
        columns=[f"{int(w * 100)}%" for w in ws])
    df.index.name = "Synergy capture"
    df.columns.name = "WACC"
    return df


def deal_trigger(
    deal_price_multiple: float = 8.0,
    wacc: float = 0.08,
    captures: Optional[List[float]] = None,
    **accretive_kw,
) -> Dict[str, object]:
    """The trigger line for ONE deal: the minimum capture that puts it in
    the buy zone under the committee's rate.

    This is the number a decision page quotes per deal: "buy only at
    capture >= 0.30 and WACC <= 10%; below that, partner or build".  The
    synergy-decay floor feeds the real-capture bar separately (see
    ``decision_page``); this trigger is the pure buy-zone bar.
    """
    caps = (np.asarray(captures, dtype=float)
            if captures is not None else DEFAULT_CAP_GRID)
    dz = buy_zone(deal_price_multiple, [float(c) for c in caps], [wacc],
                  **accretive_kw)
    col = dz.to_numpy()[:, 0]
    in_zone = [float(c) for c, ok in zip(caps, col) if bool(ok)]
    zl = zero_line([float(c) for c in caps], **accretive_kw)
    return {
        "deal_price_multiple": deal_price_multiple,
        "wacc": wacc,
        "intrinsic_multiple_at_wacc": round(intrinsic_multiple(wacc), 4),
        "in_buy_zone_captures": in_zone,
        "min_capture_in_zone": min(in_zone) if in_zone else None,
        "zero_line_by_capture": {str(k): round(float(v), 4)
                                 for k, v in zl.items()},
    }


if __name__ == "__main__":
    print("Accretion zero-line (entry multiple at which EPS effect = 0)\n")
    print(zero_line().round(4).to_string(), "\n")
    dz = deal_trigger(deal_price_multiple=8.0, wacc=0.08)
    print("Deal at 8x, 8% WACC:\n")
    for k, v in dz.items():
        print(f"  {k}: {v}")
    print("\nBuy-zone (capture x wacc) at 8x:\n")
    print(buy_zone(8.0).to_string())
