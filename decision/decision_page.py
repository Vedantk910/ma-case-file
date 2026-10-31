"""The decision page: one buy / build / partner trigger line per deal.

This is the artifact that separates a case file from a *decision tool*.  For
each deal in the book it returns a single recommendation with a quantified,
testable trigger - "buy at <= 12.1x at >= 50% capture; above that, build is
cheaper" - not a description of the deal.

The yardstick
-------------
Everything is priced in **target-EBITDA units** (target EBITDA = 10, the
case file's 100-unit base; synergy run-rate = 2.0, the case file default),
so the comparison is scale-invariant: a $16B deal and a $0.33B deal print
the *same* decision at the same entry multiple and capture.  Deal size sets
capacity, not return - the property the IRR waterfall proves.  What differs
across the 12 deals is the **sector** (e-commerce vs logistics), which sets
the in-house build and partner cost proxies.

The common value anchor is the case file's own DCF: the target's
**intrinsic value at the committee's WACC** (``surfaces.intrinsic_multiple``
x target EBITDA; 19.8x at 8%, ~198 units).  All three options deliver the
same capability; they differ in what fraction of that value they hand the
client and what they cost:

* **BUY** - full ownership (100% of intrinsic value), the target's
  *decaying* synergies (``synergy_decay``) at the deal's capture, cost =
  the entry-multiple price.  Net = V + PV(synergy at capture) - price.
* **BUILD** - 85% of the value (integration parity < owned asset,
  [unverified]), the synergy at a 60% build haircut, cost = the sector
  in-house CAPEX proxy (5-yr total, [unverified committee input]).
* **PARTNER** - 70% of the value (capability without ownership; the partner
  keeps the margin, [unverified]), zero target synergies, cost = the 5-yr
  rate-card annuity.
* **NONE** - 0; the tool says "do not do it" when no option creates value.

The recommendation is the highest net strategy; the trigger line is the
**buy price cap** - the entry multiple at which the cheaper alternative
overtakes buy - plus the alternative's name.  That is the one-liner an
essay / mandate quotes, and every number on it re-runs from the module.

The cost proxies (build CAPEX, partner rate card, the 85%/70% value
fractions) are committee inputs tagged [unverified]; what makes the page
defensible is that buy / build / partner are priced on one yardstick against
a *sourced* value anchor, so the trigger is a number a client can re-run -
not a gut call.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from data.deals import Deal, deals as all_deals
from . import surfaces, synergy_decay
from .irr_waterfall import DEFAULT_HOLD_YEARS
from model import accretive

# --- EBITDA-normalised base (matches the case file's 100-unit / 10-EBITDA) --
TARGET_EBITDA = accretive.DEFAULT_TARGET_EBITDA      # 10.0
ANNUAL_SYNERGY = accretive.DEFAULT_ANNUAL_SYNERGY    # 2.0 (20% of EBITDA)

# --- Strategy parameters ([unverified] committee inputs, priced on ONE
#     yardstick against the case file's intrinsic-value anchor) -----------
BUILD_VALUE_PARITY = 0.85     # in-house asset hands over 85% of capability value
BUILD_CAPTURE_HAIRCUT = 0.6   # build captures 60% of the buy's synergy
PARTNER_VALUE_SHARE = 0.70    # partner hands over 70% of capability value
PARTNER_RATE_CARD_PER_YR = 25.0   # rate card, in target-EBITDA units / yr
# In-house CAPEX, 5-yr total, target-EBITDA units, by sector: replicating an
# e-commerce capability (marketplace/last-mile software) is far cheaper than
# a logistics network (regional LTL, parcel carriers).
BUILD_CAPEX_BY_SECTOR = {"e-commerce": 90.0, "logistics": 160.0}
# Default entry multiple: the committee's screen input (the case file's own
# break-even band is ~8-9x, so the 8x default sits inside it).
DEFAULT_BUY_PRICE_MULTIPLE = 8.0


def intrinsic_value(wacc: float, years: int = DEFAULT_HOLD_YEARS) -> float:
    """The common value anchor: target intrinsic value at the WACC, in
    target-EBITDA units (= 10).  From the case file's DCF engine, so the
    anchor is a sourced project number, not a free parameter."""
    return surfaces.intrinsic_multiple(wacc) * TARGET_EBITDA


def strategy_economics(
    deal: Deal,
    buy_price_multiple: float = DEFAULT_BUY_PRICE_MULTIPLE,
    buy_capture: float = 0.5,
    wacc: float = 0.08,
    years: int = DEFAULT_HOLD_YEARS,
    floor: float = synergy_decay.DEFAULT_FLOOR,
) -> Dict[str, object]:
    """The three strategies (+ the do-nothing floor) priced on one yardstick.

    Every net figure is in target-EBITDA units (= 10), scale-invariant.
    """
    # Sector floor: logistics synergy compounds (network density), e-commerce
    # synergy normalises fast (traffic arbitrage) - the differentiator that
    # makes the two deal classes genuinely different, not just labels.
    floor = synergy_decay.SECTOR_FLOORS.get(deal.target_sector, floor)
    V = intrinsic_value(wacc)
    price = buy_price_multiple * TARGET_EBITDA
    sy_buy = synergy_decay.cumulative_synergy_value(
        annual_synergy=ANNUAL_SYNERGY * buy_capture,
        years=years, floor=floor, wacc=wacc)
    sy_build = synergy_decay.cumulative_synergy_value(
        annual_synergy=ANNUAL_SYNERGY * buy_capture * BUILD_CAPTURE_HAIRCUT,
        years=years, floor=floor, wacc=wacc)
    partner_cost_pv = (PARTNER_RATE_CARD_PER_YR *
                       surfaces._annuity_pv(wacc, years))
    capex = BUILD_CAPEX_BY_SECTOR[deal.target_sector]

    strategies = {
        "buy": {
            "cost": price,
            "value_share": 1.00,
            "capture": buy_capture,
            "net_pv": V + sy_buy - price,
        },
        "build": {
            "cost": capex,
            "value_share": BUILD_VALUE_PARITY,
            "capture": buy_capture * BUILD_CAPTURE_HAIRCUT,
            "net_pv": V * BUILD_VALUE_PARITY + sy_build - capex,
        },
        "partner": {
            "cost": partner_cost_pv,
            "value_share": PARTNER_VALUE_SHARE,
            "capture": 0.0,
            "net_pv": V * PARTNER_VALUE_SHARE - partner_cost_pv,
        },
        "none": {"cost": 0.0, "value_share": 0.0, "capture": 0.0, "net_pv": 0.0},
    }
    return {
        "deal": f"{deal.acquirer} -> {deal.target} ({deal.year})",
        "sector": deal.target_sector,
        "deal_value_billion_usd": deal.deal_value_billion_usd,
        "buy_price_multiple": buy_price_multiple,
        "wacc": wacc,
        "intrinsic_value": round(V, 2),
        "strategies": strategies,
        "params": {
            "build_value_parity": BUILD_VALUE_PARITY,
            "build_capture_haircut": BUILD_CAPTURE_HAIRCUT,
            "partner_value_share": PARTNER_VALUE_SHARE,
            "partner_rate_card_per_yr": PARTNER_RATE_CARD_PER_YR,
            "build_capex": capex,
            "tag": "[unverified] committee inputs, one yardstick, sourced V",
        },
    }


def buy_price_cap(
    deal: Deal,
    buy_capture: float = 0.5,
    wacc: float = 0.08,
    years: int = DEFAULT_HOLD_YEARS,
    floor: float = synergy_decay.DEFAULT_FLOOR,
    price_grid: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """The entry multiple at which the cheapest alternative overtakes buy.

    Sweep the entry multiple; the cap is the highest price at which BUY
    still nets at least as much as the best of build / partner / none.
    Returns the cap and the alternative that wins past it - the "above
    that, X is cheaper" half of the trigger line.
    """
    grid = (np.asarray(price_grid, dtype=float) if price_grid is not None
            else np.arange(4.0, 20.0 + 1e-9, 0.25))
    eco = {p: strategy_economics(deal, buy_price_multiple=float(p),
                                 buy_capture=buy_capture, wacc=wacc,
                                 years=years, floor=floor) for p in grid}
    winners = []
    for p in grid:
        s = eco[p]["strategies"]
        if s["buy"]["net_pv"] >= max(s["build"]["net_pv"],
                                     s["partner"]["net_pv"], 0.0):
            winners.append(p)
    cap = float(max(winners)) if winners else 0.0
    s = eco[cap if cap > 0 else grid[0]]["strategies"]
    alt = ("build" if s["build"]["net_pv"] >= s["partner"]["net_pv"]
           else "partner")
    return {"cap": cap, "alternative": alt,
            "alt_pv": s[alt]["net_pv"], "buy_pv_at_cap": s["buy"]["net_pv"]}


def recommend(
    deal: Deal,
    buy_price_multiple: float = DEFAULT_BUY_PRICE_MULTIPLE,
    buy_capture: float = 0.5,
    wacc: float = 0.08,
    years: int = DEFAULT_HOLD_YEARS,
    floor: float = synergy_decay.DEFAULT_FLOOR,
) -> Dict[str, object]:
    """One recommendation + quantified trigger line for a single deal."""
    eco = strategy_economics(deal, buy_price_multiple=buy_price_multiple,
                             buy_capture=buy_capture, wacc=wacc, years=years,
                             floor=floor)
    s = eco["strategies"]
    winner = max(s, key=lambda k: s[k]["net_pv"])
    cap_info = buy_price_cap(deal, buy_capture=buy_capture, wacc=wacc,
                            years=years, floor=floor)
    min_cap_zone = surfaces.deal_trigger(buy_price_multiple, wacc)[
        "min_capture_in_zone"]

    if winner == "buy":
        trigger = (f"BUY at <= {cap_info['cap']:.1f}x with "
                   f">= {buy_capture*100:.0f}% capture; above that, "
                   f"{cap_info['alternative']} is cheaper")
    else:
        trigger = (f"at {buy_price_multiple:.0f}x, {winner} is cheaper than "
                   f"buy; buy only at <= {cap_info['cap']:.1f}x")
    return {
        "deal": eco["deal"],
        "sector": eco["sector"],
        "deal_value_billion_usd": eco["deal_value_billion_usd"],
        "buy_price_multiple": buy_price_multiple,
        "recommendation": winner.upper(),
        "trigger": trigger,
        "buy_price_cap": cap_info["cap"],
        "cap_alternative": cap_info["alternative"],
        "min_capture_in_zone": min_cap_zone,
        "net_pv_by_strategy": {k: round(v["net_pv"], 2)
                                for k, v in s.items()},
        "strategies": s,
    }


def page(
    deals: Optional[List[Deal]] = None,
    buy_price_multiple: float = DEFAULT_BUY_PRICE_MULTIPLE,
    buy_capture: float = 0.5,
    wacc: float = 0.08,
    years: int = DEFAULT_HOLD_YEARS,
    floor: float = synergy_decay.DEFAULT_FLOOR,
) -> pd.DataFrame:
    """One row per deal: recommendation + trigger + the net-PV split.

    This frame is what ``report/decision_page.md`` prints.  The per-deal
    difference is the sector: e-commerce and logistics deals carry
    different build CAPEX proxies, so their triggers differ even at the
    same entry multiple and capture - the state of the page, not noise.
    """
    book = deals if deals is not None else all_deals()
    rows = []
    for d in book:
        r = recommend(d, buy_price_multiple=buy_price_multiple,
                      buy_capture=buy_capture, wacc=wacc, years=years,
                      floor=floor)
        rows.append({
            "Deal": r["deal"],
            "Sector": r["sector"],
            "Value ($B)": round(r["deal_value_billion_usd"], 2),
            "Buy @": f"{r['buy_price_multiple']:.0f}x",
            "Recommendation": r["recommendation"],
            "Buy cap (x)": f"{r['buy_price_cap']:.1f}",
            "Alt past cap": r["cap_alternative"],
            "Min cap in zone": (f"{r['min_capture_in_zone']*100:.0f}%"
                                if r["min_capture_in_zone"] is not None
                                else "n/a"),
            "PV buy": r["net_pv_by_strategy"]["buy"],
            "PV build": r["net_pv_by_strategy"]["build"],
            "PV partner": r["net_pv_by_strategy"]["partner"],
            "Trigger": r["trigger"],
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print(page().to_string(index=False))
