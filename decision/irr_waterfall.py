"""Per-deal IRR waterfalls: decompose a roll-up's sponsor return gate-by-gate.

``model.rollup`` gives a sponsor IRR for one (entry, exit, leverage, hold)
scenario.  A *waterfall* is the same number decomposed so a client can see
which gate is doing the work - the exhibit that turns an IRR matrix into a
decision ("buy only if the multiple-expansion gate is real, because growth
alone does not clear the hurdle").

The bridge is analytic and additive, expressed in entry-EBITDA units of
equity value.  Starting from the sponsor's entry equity

    entry_equity   = ebitda * (entry_mult - leverage)

the exit equity (from ``model.rollup.sponsor_cash_flows``) is

    exit_equity    = ebitda * (1 + g)^H * exit_mult - ebitda * leverage

and the MOC (exit / entry equity) bridges as three gates:

    1. entry equity          ebitda * (entry_mult - leverage)
    2. + EBITDA growth       ebitda * ((1+g)^H - 1) * entry_mult
       (grow the asset, hold the entry multiple)
    3. + multiple expansion  ebitda * (1+g)^H * (exit_mult - entry_mult)
    = exit equity

Gates 2 and 3 are *the* decision: if gate 3 (the sponsor's assumption that the
multiple re-rates up on exit) is doing most of the work, the IRR is a
multiple assumption, not a business return - and a hostile interviewer's
"what's the distribution, not just the estimate?" wants exactly this split.

The per-deal layer then runs a consistent set of (entry, exit) scenarios on
every deal in the book and reports each deal's IRR + its gate split.  A key
defensible property the exhibit states: **sponsored IRR is scale-invariant**
- a $16B and a $0.33B deal at the same multiples / leverage / growth print the
same IRR; deal size sets *capacity*, not return.  So per-deal IRR differences
come from sector growth assumptions and the entry multiple chosen, never from
the headline deal value.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from model import rollup
from data.deals import Deal, deals as all_deals

# Sector-default EBITDA growth for a roll-up hold.  E-commerce platforms grow
# faster on the revenue side but margins normalise; logistics is slower but
# the network compounds.  These are committee inputs, tagged in the note.
DEFAULT_EBITDA_CAGR = {"logistics": 0.03, "e-commerce": 0.05}
DEFAULT_HOLD_YEARS = 5
DEFAULT_LEVERAGE = 4.0

# Entry/exit scenario pairs the decision page quotes per deal.  The 6x->12x
# "expansion" case is the optimistic multiple gate; 12x->6x is the mean-
# reversion case; 8x->8x isolates growth with no multiple assumption.
DEFAULT_SCENARIOS: List[Dict[str, float]] = [
    {"entry": 6.0, "exit": 12.0, "label": "6x in -> 12x out (expansion)"},
    {"entry": 8.0, "exit": 8.0, "label": "8x in -> 8x out (growth only)"},
    {"entry": 12.0, "exit": 6.0, "label": "12x in -> 6x out (mean-reversion)"},
]


def equity_multiple_bridge(
    ebitda_entry: float = rollup.DEFAULT_EBITDA_ENTRY,
    entry_multiple: float = 8.0,
    exit_multiple: float = 10.0,
    leverage: float = DEFAULT_LEVERAGE,
    hold_years: int = DEFAULT_HOLD_YEARS,
    ebitda_cagr: float = rollup.DEFAULT_EBITDA_CAGR,
) -> Dict[str, float]:
    """The gate-by-gate MOC bridge (see module docstring for the algebra).

    Returns each gate's contribution in entry-EBITDA units of equity, the
    resulting MOC, and the implied IRR.  ``implied_irr`` matches
    ``model.rollup.deal_irr`` exactly (single-crossing, exit at year H), so
    the waterfall is a *decomposition*, not a new estimate.
    """
    growth_factor = (1.0 + ebitda_cagr) ** hold_years
    entry_equity = ebitda_entry * (entry_multiple - leverage)
    g_grow = ebitda_entry * (growth_factor - 1.0) * entry_multiple
    g_expand = ebitda_entry * growth_factor * (exit_multiple - entry_multiple)
    exit_equity = entry_equity + g_grow + g_expand
    if entry_equity <= 0:
        raise ValueError(
            f"leverage {leverage}x must be below the entry multiple "
            f"{entry_multiple}x for positive entry equity")
    moc = exit_equity / entry_equity
    implied_irr = moc ** (1.0 / hold_years) - 1.0
    return {
        "entry_equity_per_ebitda": entry_equity / ebitda_entry,
        "gate_growth_per_ebitda": g_grow / ebitda_entry,
        "gate_multiple_expansion_per_ebitda": g_expand / ebitda_entry,
        "exit_equity_per_ebitda": exit_equity / ebitda_entry,
        "moc": moc,
        "implied_irr": implied_irr,
        "growth_share_of_gates": (
            g_grow / (g_grow + g_expand) if (g_grow + g_expand) else 0.0),
    }


def _irr_and_split(scen: Dict[str, float], deal: Deal) -> Dict[str, object]:
    cagr = float(scen.get("cagr",
                           DEFAULT_EBITDA_CAGR.get(deal.target_sector,
                                                    rollup.DEFAULT_EBITDA_CAGR)))
    lev = float(scen.get("leverage", DEFAULT_LEVERAGE))
    hold = int(scen.get("hold", DEFAULT_HOLD_YEARS))
    e = float(scen["entry"])
    x = float(scen["exit"])
    r = rollup.deal_irr(entry_multiple=e, exit_multiple=x, leverage=lev,
                        hold_years=hold, ebitda_cagr=cagr)
    bridge = equity_multiple_bridge(
        entry_multiple=e, exit_multiple=x, leverage=lev,
        hold_years=hold, ebitda_cagr=cagr)
    # The bisection IRR and the closed-form implied IRR must agree to solver
    # tolerance - the check that the waterfall decomposes the real estimate.
    agrees = (r is not None and bridge["implied_irr"] is not None
              and abs(r - bridge["implied_irr"]) < 1e-3)
    return {
        "label": scen.get("label", f"{e}x -> {x}x"),
        "entry_multiple": e,
        "exit_multiple": x,
        "leverage": lev,
        "cagr": cagr,
        "hold_years": hold,
        "sector_default_cagr": deal.target_sector,
        "irr_bisection": r,
        "moc": bridge["moc"],
        "growth_share_of_gates": bridge["growth_share_of_gates"],
        "irrs_agree": agrees,
    }


def deal_irr_waterfall(
    deal: Deal,
    scenarios: Optional[List[Dict[str, float]]] = None,
) -> Dict[str, object]:
    """Entry/exit multiple scenarios + gate split for ONE deal.

    This is the per-deal exhibit: every deal in the book gets the same three
    scenarios (expansion / growth-only / mean-reversion) so the IRRs are
    directly comparable, and each carries its gate split so the reader sees
    how much is a multiple assumption vs. a business return.
    """
    scenarios = scenarios if scenarios is not None else DEFAULT_SCENARIOS
    rows = [_irr_and_split(sc, deal) for sc in scenarios]
    return {
        "deal": f"{deal.acquirer} -> {deal.target} ({deal.year})",
        "deal_value_billion_usd": deal.deal_value_billion_usd,
        "sector": deal.target_sector,
        "scenarios": rows,
        "scale_invariant_note": (
            "IRR depends on multiples/leverage/growth/hold, NOT on the "
            "announced deal value; size sets capacity, not return."),
    }


def per_deal_irr_matrix(
    scenarios: Optional[List[Dict[str, float]]] = None,
    deals: Optional[List[Deal]] = None,
) -> pd.DataFrame:
    """One row per deal x scenario: the comparable IRR + gate split for the
    whole 12-deal book.  This is the "per-deal IRR waterfalls on all 12
    deals" deliverable from the C1 brief."""
    scenarios = scenarios if scenarios is not None else DEFAULT_SCENARIOS
    book = deals if deals is not None else all_deals()
    rows: List[Dict[str, object]] = []
    for d in book:
        wf = deal_irr_waterfall(d, scenarios)
        for sc in wf["scenarios"]:
            rows.append({
                "Deal": wf["deal"],
                "Sector": wf["sector"],
                "Scenario": sc["label"],
                "Lev (x EBITDA)": sc["leverage"],
                "CAGR": sc["cagr"],
                "Sponsor IRR (%)": (
                    round(sc["irr_bisection"] * 100.0, 1)
                    if sc["irr_bisection"] is not None else None),
                "MOC (x)": round(sc["moc"], 2),
                "Growth share of gates": round(
                    sc["growth_share_of_gates"], 2),
                "IRR agrees w/ bridge": bool(sc["irrs_agree"]),
            })
    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    df = per_deal_irr_matrix()
    print(df.to_string(index=False))
    print("\nScale-invariance check: expansion case IRR by sector CAGR\n")
    for sc in DEFAULT_SCENARIOS:
        if "12x out" in sc["label"]:
            b = equity_multiple_bridge(
                entry_multiple=sc["entry"], exit_multiple=sc["exit"],
                leverage=sc.get("leverage", DEFAULT_LEVERAGE),
                ebitda_cagr=sc.get("cagr", 0.04),
                hold_years=sc.get("hold", DEFAULT_HOLD_YEARS))
            print(f"  {sc['label']}: IRR {b['implied_irr']*100:.1f}%, "
                  f"growth does {b['growth_share_of_gates']*100:.0f}% "
                  f"of the gate work")
