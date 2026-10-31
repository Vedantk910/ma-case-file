"""Synergy decay over Y1..Y5: full capture in year 1, eroding to a floor.

The case file's accretion model takes synergy capture as a *scalar* (0/25/50/
100% forever).  Real deals are not like that: the stated synergy is a
run-rate, and integration friction, cost counter-measures and customer
attrition claw part of it back.  Literature-typical shape for logistics
roll-ups is **full Y1 -> 40-60% by Y5** [unverified: direction of the curve is
the consensus; the exact floor is a committee input, not a sourced constant].

The decay model here:

    f(t) = 1 - (1 - floor) * (t - 1) / (H - 1)      t in 1..H   (linear)

so the realized synergy in year t is ``S * f(t)``: 100% of the stated amount
in year 1, fading to ``floor * S`` by year H (default 5, default floor 0.5).
Everything else about the deal is unchanged from ``model.accretive``: the
target's base net income runs every year at full value; only the synergy
term decays.

What the decay buys us: every deal can now say "accretive for N years, then
inverts" - the number a buy-vs-build decision actually needs, not "accretive
in year one".
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from model import accretive

# Default decay profile: full Y1, 50% by Y5 (midpoint of the 40-60% band).
DEFAULT_DECAY_YEARS = 5
DEFAULT_FLOOR = 0.50
DEFAULT_SCHEDULE = "linear"        # "linear" | "step"

# Literature-anchored floors by sector [unverified: sector split is our own
# convention on top of the consensus band; tag it, don't cite a number].
SECTOR_FLOORS = {
    "logistics": 0.50,   # roll-up synergy decays slow: network density compounds
    "e-commerce": 0.40,  # platform synergy decays fast: traffic arbitrage normalises
}


def capture_profile(
    years: int = DEFAULT_DECAY_YEARS,
    floor: float = DEFAULT_FLOOR,
    schedule: str = DEFAULT_SCHEDULE,
) -> Dict[int, float]:
    """Realized-synergy fraction of the stated run-rate, by deal year.

    year 1 is always 1.0 (the stated synergy is a year-1 run-rate); by
    ``years`` it has decayed to ``floor``.  "linear" interpolates evenly;
    "step" holds 1.0 for the first half and ``floor`` for the rest (a
    coarser ablation so the linear shape's edge is auditable).
    """
    if years < 2:
        raise ValueError("need >= 2 years for a decay profile")
    if not 0.0 <= floor <= 1.0:
        raise ValueError("floor must be in [0, 1]")
    prof: Dict[int, float] = {}
    for t in range(1, years + 1):
        if t == 1:
            prof[t] = 1.0
        elif schedule == "linear":
            frac = (t - 1) / (years - 1)
            prof[t] = 1.0 - (1.0 - floor) * frac
        else:  # step
            prof[t] = 1.0 if t <= years // 2 else floor
    return prof


def yearly_accretions(
    years: int = DEFAULT_DECAY_YEARS,
    floor: float = DEFAULT_FLOOR,
    schedule: str = DEFAULT_SCHEDULE,
    acq_net_income: float = accretive.DEFAULT_ACQ_NET_INCOME,
    target_ebitda: float = accretive.DEFAULT_TARGET_EBITDA,
    multiple: float = 8.0,
    ni_per_ebitda: float = accretive.DEFAULT_TARGET_NI_PER_EBITDA,
    annual_synergy: float = accretive.DEFAULT_ANNUAL_SYNERGY,
    debt_share: float = accretive.DEFAULT_DEBT_SHARE_OF_FUNDING,
    debt_rate: float = accretive.DEFAULT_DEBT_RATE,
) -> List[float]:
    """Year-1..H EPS accretion, synergy decaying per ``capture_profile``.

    Mirrors ``model.accretive.accretion`` but with the capture rate set to
    ``f(t)`` each year, so the series is the decay's signature: positive,
    falling, possibly crossing zero inside the hold.
    """
    prof = capture_profile(years, floor, schedule)
    return [
        accretive.accretion(
            acq_net_income, target_ebitda, multiple, ni_per_ebitda,
            annual_synergy, prof[t], debt_share, debt_rate)
        for t in range(1, years + 1)
    ]


def accretive_years(
    years: int = DEFAULT_DECAY_YEARS,
    floor: float = DEFAULT_FLOOR,
    schedule: str = DEFAULT_SCHEDULE,
    **kw,
) -> int:
    """How many years the deal stays accretive before it inverts.

    Counts the *first consecutive* years with accretion > 0 starting from
    year 1 (a deal that is dilutive from day one stays dilutive - the decay
    only makes it worse).  This is the "accretive for N years, then inverts"
    number, and it is the one that closes the buy-vs-build triangle.
    """
    series = yearly_accretions(years, floor, schedule, **kw)
    n = 0
    for a in series:
        if a <= 0.0:
            break
        n += 1
    return n


def cumulative_synergy_value(
    annual_synergy: float = accretive.DEFAULT_ANNUAL_SYNERGY,
    years: int = DEFAULT_DECAY_YEARS,
    floor: float = DEFAULT_FLOOR,
    schedule: str = DEFAULT_SCHEDULE,
    wacc: float = 0.08,
) -> float:
    """PV of the *decaying* synergy stream at the committee discount rate.

    The scalar-capture world prices the synergy as a perpetual
    ``S*c/(1 - ...)`; the decay world prices exactly what the client gets:
    S*f(1)..S*f(H), discounted.  This is the dollar value the decision page
    compares the buy premium against.
    """
    if wacc <= 0:
        raise ValueError("wacc must be > 0")
    prof = capture_profile(years, floor, schedule)
    return sum(annual_synergy * prof[t] / (1.0 + wacc) ** t
               for t in range(1, years + 1))


def decay_table(
    multiples: Optional[List[float]] = None,
    years: int = DEFAULT_DECAY_YEARS,
    floor: float = DEFAULT_FLOOR,
    **kw,
) -> pd.DataFrame:
    """Per-multiple decay signature: Y1..Y5 accretion + accretive-years count.

    Rows = entry multiples; columns = the per-year accretion fractions plus
    ``accretive_years`` - the one-row-per-multiple exhibit a decision page
    quotes ("at 8x, accretive for 4 of 5 years; at 10x, 2 of 5; at 12x,
    zero").
    """
    multiples = (np.asarray(multiples, dtype=float)
                 if multiples is not None else accretive.DEFAULT_MULTIPLES)
    rows = []
    for m in multiples:
        series = yearly_accretions(years, floor, DEFAULT_SCHEDULE,
                                   multiple=float(m), **kw)
        row = {f"Y{t}": series[t - 1] for t in range(1, years + 1)}
        row["accretive_years"] = accretive_years(years, floor, DEFAULT_SCHEDULE,
                                                 multiple=float(m), **kw)
        rows.append(row)
    df = pd.DataFrame(rows, index=[f"{int(m)}x" for m in multiples])
    df.index.name = "Entry EV/EBITDA"
    return df
