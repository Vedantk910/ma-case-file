"""100-unit EPS accretion/dilution model (project P3).

Convention
----------
Model a *standardised* acquirer with 100 shares outstanding and a base net
income. The target is bought at a chosen EV/EBITDA multiple, partially with
debt. The accretion of the deal on year-1 EPS is::

    accretion_pct = (acq_net_income + target_net_income_after_synergy
                     - financing_cost) / acq_net_income - 1

A positive value = accretive (EPS goes up), negative = dilutive.

Because a target's net income cannot be back-solved from a multiple without
the target's own margin, this model parameterises the target's contribution
by its **net-income-on-EBITDA conversion** (``target_ni_per_ebitda``), i.e.
target net income = EBITDA * conversion. This keeps the grid analytic and
reproducible. See ``accretion`` / ``accretion_grid`` docstrings for the
exact inputs.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Grid defaults
# ---------------------------------------------------------------------------
DEFAULT_MULTIPLES = np.arange(6.0, 12.0 + 1e-9, 1.0)     # 6,7,8,9,10,11,12
DEFAULT_SYNERGY_CAPTURES = np.array([0.0, 0.25, 0.50, 1.00])
DEFAULT_ACQ_NET_INCOME = 100.0          # base acquirer net income (units)
DEFAULT_TARGET_EBITDA = 10.0            # target trailing EBITDA (units)
DEFAULT_TARGET_NI_PER_EBITDA = 0.30     # target net-income-on-EBITDA
DEFAULT_ANNUAL_SYNERGY = 2.0           # stated annual synergy, full capture
DEFAULT_DEBT_SHARE_OF_FUNDING = 0.60   # fraction of deal value funded by debt
DEFAULT_DEBT_RATE = 0.05               # after-tax financing rate
DEFAULT_ACQ_SHARES = 100.0             # acquirer shares (100-unit model)


def target_enterprise_value(ebitda: float, multiple: float) -> float:
    """Enterprise value of the target at a given EV/EBITDA multiple.

    EV = EBITDA * multiple.
    """
    if multiple < 0:
        raise ValueError("multiple must be >= 0")
    return ebitda * multiple


def financing_cost(enterprise_value: float,
                   debt_share: float,
                   rate: float) -> float:
    """After-tax interest cost on the debt-funded portion of the deal.

    cost = EV * debt_share * rate

    (Equity-funded portion carries no explicit cost in this first-year
     screen; financing_cost captures the debt piece only.)
    """
    return enterprise_value * debt_share * rate


def acquirer_net_income_after(
    acq_net_income: float,
    target_ni_after_synergy: float,
    fin_cost: float,
) -> float:
    """Combined year-1 net income after the deal.

    = acquirer net income + target net income after synergy - financing cost.
    """
    return acq_net_income + target_ni_after_synergy - fin_cost


def target_ni_after_synergy(
    ebitda: float,
    ni_per_ebitda: float,
    annual_synergy: float,
    synergy_capture: float,
) -> float:
    """Target contribution to the acquirer's bottom line.

    target_ni = EBITDA * ni_per_ebitda + annual_synergy * capture

    The synergy term is applied at the stated capture rate (0/25/50/100%).
    Assumes the synergy is a pre-tax P&L contribution flowing to net income.
    """
    if not 0.0 <= synergy_capture <= 1.0:
        raise ValueError("synergy_capture must be in [0, 1]")
    return ebitda * ni_per_ebitda + annual_synergy * synergy_capture


def accretion(
    acq_net_income: float = DEFAULT_ACQ_NET_INCOME,
    target_ebitda: float = DEFAULT_TARGET_EBITDA,
    multiple: float = 8.0,
    ni_per_ebitda: float = DEFAULT_TARGET_NI_PER_EBITDA,
    annual_synergy: float = DEFAULT_ANNUAL_SYNERGY,
    synergy_capture: float = DEFAULT_SYNERGY_CAPTURES[2],
    debt_share: float = DEFAULT_DEBT_SHARE_OF_FUNDING,
    debt_rate: float = DEFAULT_DEBT_RATE,
) -> float:
    """Year-1 EPS accretion/dilution from a single transaction.

    Returns the accretion fraction (e.g. +0.042 = +4.2% accretive). The EPS
    effect equals the net-income effect divided by the base acquirer income,
    because a stock-for-stock 100-unit buy keeps the acquirer's own shares
    constant and adds the target's income as a percentage of that base.

    Accretion > 0  -> the deal lifts year-1 EPS.
    Accretion < 0  -> the deal is dilutive.
    """
    ev = target_enterprise_value(target_ebitda, multiple)
    fin_cost = financing_cost(ev, debt_share, debt_rate)
    tni = target_ni_after_synergy(
        target_ebitda, ni_per_ebitda, annual_synergy, synergy_capture)
    return (acq_net_income + tni - fin_cost) / acq_net_income - 1.0


def accretion_grid(
    multiples: Optional[List[float]] = None,
    synergy_captures: Optional[List[float]] = None,
    acq_net_income: float = DEFAULT_ACQ_NET_INCOME,
    target_ebitda: float = DEFAULT_TARGET_EBITDA,
    ni_per_ebitda: float = DEFAULT_TARGET_NI_PER_EBITDA,
    annual_synergy: float = DEFAULT_ANNUAL_SYNERGY,
    debt_share: float = DEFAULT_DEBT_SHARE_OF_FUNDING,
    debt_rate: float = DEFAULT_DEBT_RATE,
) -> pd.DataFrame:
    """Sweep the multiple x synergy grid and return the accretion% table.

    Rows = synergy capture (0/25/50/100%), columns = EV/EBITDA multiple
    (6x..12x). Each cell is the year-1 EPS accretion/dilution percentage.

    Parameters
    ----------
    multiples : list of EV/EBITDA multiples to sweep across the columns.
    synergy_captures : list of capture fractions (0..1) down the rows.
    All other params default to the module-level 100-unit constants.
    """
    multiples = np.asarray(multiples, dtype=float) if multiples is not None else DEFAULT_MULTIPLES
    synergy_captures = (np.asarray(synergy_captures, dtype=float)
                       if synergy_captures is not None else DEFAULT_SYNERGY_CAPTURES)

    grid = np.empty((len(synergy_captures), len(multiples)))
    for i, cap in enumerate(synergy_captures):
        for j, mult in enumerate(multiples):
            grid[i, j] = accretion(
                acq_net_income, target_ebitda, mult, ni_per_ebitda,
                annual_synergy, cap, debt_share, debt_rate)

    df = pd.DataFrame(grid,
                      index=(f"{int(c*100)}% capture" for c in synergy_captures),
                      columns=[f"{int(m)}x" for m in multiples])
    df.columns.name = "EV/EBITDA multiple"
    df.index.name = "Synergy capture"
    return df


def best_cell(df: pd.DataFrame) -> dict:
    """Locate the single most accretive cell in an ``accretion_grid`` frame.

    Returns a dict with multiple, capture, accretion and whether the whole
    grid is accretive. This is the number a CV bullet would cite.
    """
    values = df.to_numpy()
    idx = int(np.argmax(values))
    r, c = np.unravel_index(idx, values.shape)
    cell = {
        "multiple": str(df.columns[c]),
        "capture": str(df.index[r]),
        "accretion_pct": float(values[r, c]),
        "grid_min_pct": float(values.min()),
        "grid_max_pct": float(values.max()),
        "all_accretive": bool((values > 0).all()),
    }
    return cell


if __name__ == "__main__":
    grid = accretion_grid()
    print("Year-1 EPS accretion/dilution (%), 100-unit model\n")
    print((grid * 100).round(2).to_string())
    print("\nBest cell:", best_cell(grid))
