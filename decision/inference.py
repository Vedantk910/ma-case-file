"""Elite layer: distributions, not point estimates, on the decision numbers.

The decision tool's headline outputs (buy price cap, roll-up IRR, strategy
net PVs, accretive years) are deterministic *given the committee inputs* -
so the honest elite question is: **over the realistic range of those
inputs, what is the distribution of the headline number, and does the
decision survive the multiple-scenario family the screen actually tried?**

Three tools, all seeded and offline:

* **Input-prior bootstrap** - the committee inputs are assumptions, not
  data, so we put honest prior bands on them (the ``INPUT_BANDS`` below)
  and resample them with a seeded RNG.  Every headline number comes back
  as P10/P50/P90 - the CI the one-pager quotes.  Deterministic for a seed,
  so the note's numbers reproduce by one command.

* **Prior-predictive family check (the deflated-IRR analog)** - the screen
  tried M roll-up scenarios on one panel and would naturally cite the best
  one (the expansion case).  Under the *null* "no edge" world - zero EBITDA
  growth and a flat exit multiple - the expected best-of-M multiple-on-cost
  is exactly 1.0, so asking "how likely is a best-of-M MOC >= observed,
  purely from input luck?" is a well-defined prior-predictive p-value.
  The family-adjusted verdict survives only if that mass is small - the
  "deflated" read, the one a hostile reviewer wants.

* **Bootstrap on the IRR directly** - recompute the bisection IRR on every
  resampled input draw and report the IRR's own P10/P50/P90.  (The MOC and
  IRR orderings agree to the solver tolerance, so the CI on the MOC and the
  CI on the IRR are the same object seen two ways.)
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

from . import decision_page as dp
from . import irr_waterfall
from model import rollup
from data.deals import Deal, deals as all_deals

# Realistic committee-input bands.  These are [unverified] assumption ranges,
# not sourced constants: the bootstrap says "across plausible committee
# inputs the headline is THIS wide", which is the defensible form.
INPUT_BANDS: Dict[str, tuple] = {
    "capture": (0.25, 0.75),          # synergy capture the mandate can hold
    "cagr": (0.02, 0.06),             # hold-period EBITDA growth
    "exit_mult_delta": (-1.0, 2.0),   # exit multiple vs entry (-1x .. +2x)
    "leverage": (3.0, 5.0),           # x EBITDA
    "build_capex_ecom": (60.0, 120.0),   # target-EBITDA units, 5-yr total
    "build_capex_logi": (100.0, 220.0),
    "partner_rate_card": (15.0, 35.0),   # $/yr in target-EBITDA units
}


def _resample_inputs(seed: int, n: int = 1, rng: Optional[np.random.Generator] = None,
                     **over: float) -> np.ndarray:
    """One column of uniform draws per band, shaped (n, len(bands))."""
    rng = rng if rng is not None else np.random.default_rng(seed)
    keys = list(INPUT_BANDS) + sorted(list(over))
    cols = []
    for k in keys:
        lo, hi = over.get(k, INPUT_BANDS[k])
        cols.append(rng.uniform(lo, hi, size=n))
    return np.column_stack(cols)


def input_bootstrap(
    deal: Deal,
    n: int = 2000,
    seed: int = 0,
    hold_years: int = irr_waterfall.DEFAULT_HOLD_YEARS,
) -> Dict[str, object]:
    """P10/P50/P90 of every headline decision number over the input bands.

    One draw -> one full re-evaluation of the deal's decision (buy cap,
    IRR, strategy PVs, accretive years); the percentiles across draws are
    the CI the note quotes.  ``seed`` fixes the order, so the number in the
    report is reproducible by one command.
    """
    keys = list(INPUT_BANDS)
    X = _resample_inputs(seed, n)
    caps, cags, exits, levs = X[:, 0], X[:, 1], X[:, 2], X[:, 3]
    bcap_ecom, bcap_logi, prate = X[:, 4], X[:, 5], X[:, 6]

    def eval_one(i: int) -> Dict[str, float]:
        band = {  # per-sector live values from this draw
            "e-commerce": bcap_ecom[i], "logistics": bcap_logi[i]}
        dpage = _decision_page_with_overrides(
            deal, capture=caps[i], build_capex=band, partner_rate=prate[i])
        irr_exp = irr_waterfall.equity_multiple_bridge(
            entry_multiple=6.0, exit_multiple=6.0 + exits[i],
            leverage=levs[i], ebitda_cagr=cags[i], hold_years=hold_years)
        return {
            "buy_cap": dpage["buy_cap"],
            "irr_expansion": irr_exp["implied_irr"],
            "pv_buy": dpage["pv_buy"],
            "pv_build": dpage["pv_build"],
            "pv_partner": dpage["pv_partner"],
        }

    cols: Dict[str, List[float]] = {k: [] for k in
                                    ("buy_cap", "irr_expansion", "pv_buy",
                                     "pv_build", "pv_partner")}
    for i in range(n):
        one = eval_one(i)
        for k in cols:
            cols[k].append(one[k])
    arr = {k: np.asarray(v, dtype=float) for k, v in cols.items()}
    return {
        "n": int(n),
        "seed": int(seed),
        "p10": {k: round(float(np.percentile(v, 10)), 4)
                for k, v in arr.items()},
        "p50": {k: round(float(np.percentile(v, 50)), 4)
                for k, v in arr.items()},
        "p90": {k: round(float(np.percentile(v, 90)), 4)
                for k, v in arr.items()},
    }


def _decision_page_with_overrides(deal: Deal, capture: float,
                                  build_capex: Dict[str, float],
                                  partner_rate: float) -> Dict[str, float]:
    """Re-run the decision page's economics with a single draw's inputs.

    Mirrors ``decision_page.strategy_economics`` but with the committee
    constants replaced by the resampled values - that is what makes the
    bootstrap a *prior predictive* distribution, not a resample of data.
    """
    import decision.decision_page as dp

    V = dp.intrinsic_value(0.08)
    price = dp.DEFAULT_BUY_PRICE_MULTIPLE * dp.TARGET_EBITDA
    sy_buy = dp.synergy_decay.cumulative_synergy_value(
        annual_synergy=dp.ANNUAL_SYNERGY * capture, years=5,
        floor=dp.synergy_decay.SECTOR_FLOORS[deal.target_sector], wacc=0.08)
    build_cap = capture * dp.BUILD_CAPTURE_HAIRCUT
    sy_build = dp.synergy_decay.cumulative_synergy_value(
        annual_synergy=dp.ANNUAL_SYNERGY * build_cap, years=5,
        floor=dp.synergy_decay.SECTOR_FLOORS[deal.target_sector], wacc=0.08)
    partner_cost = partner_rate * dp.surfaces._annuity_pv(0.08, 5)
    pv_buy = V + sy_buy - price
    pv_build = V * dp.BUILD_VALUE_PARITY + sy_build - build_capex[deal.target_sector]
    pv_partner = V * dp.PARTNER_VALUE_SHARE - partner_cost

    # the buy cap: highest 8x-style entry price where buy still wins the best
    # alternative, recomputed on THIS draw's inputs
    def pv_at_price(mult: float) -> float:
        p = mult * dp.TARGET_EBITDA
        return V + sy_buy - p

    def alt_best(mult: float) -> float:
        p = mult * dp.TARGET_EBITDA
        return max(pv_build, pv_partner, 0.0)

    best = 0.0
    for mult in np.arange(4.0, 20.0 + 1e-9, 0.25):
        if pv_at_price(float(mult)) >= alt_best(float(mult)):
            best = float(mult)
    return {"buy_cap": best, "pv_buy": pv_buy, "pv_build": pv_build,
            "pv_partner": pv_partner}


def prior_predictive_irr(
    n: int = 2000,
    seed: int = 0,
    family: Sequence[Dict[str, float]] = None,
    sigma_growth: float = 0.02,
    sigma_exit_delta: float = 1.0,
) -> Dict[str, object]:
    """The deflated-IRR analog: how likely is the observed best MOC to have
    happened purely from input luck, under a *no-systematic-edge* null?

    The screen tried M scenarios and would cite the best (the expansion case).
    A hostile reviewer asks: "if the committee's growth and multiple-expansion
    assumptions are just optimistic *noise* with no real edge, how often does
    the **best of M** MOC still print at least as high as the observed best?"

    The null keeps realistic committee uncertainty (EBITDA growth and exit
    multiple-delta are normal around a zero-edge mean, leverage fixed) so the
    null MOC has real spread - a strict no-edge null would make MOC
    identically 1.0 and the test vacuous.  Mass = the prior-predictive p:
    small mass means the observed expansion MOC sits far out in the tail of
    the no-edge world, i.e. the edge is not an input-luck artifact.  This is
    the "deflated" read - the one a reviewer wants before trusting the best
    scenario.
    """
    if family is None:
        family = irr_waterfall.DEFAULT_SCENARIOS
    hold = irr_waterfall.DEFAULT_HOLD_YEARS
    lev = irr_waterfall.DEFAULT_LEVERAGE
    base = {s["label"]: irr_waterfall.equity_multiple_bridge(
        entry_multiple=s["entry"], exit_multiple=s["exit"],
        leverage=s.get("leverage", lev),
        # the bridge wants a scalar; irr_waterfall's sector map is a dict the
        # scenario family does not key by sector, so fall back to the
        # rollup's committee default (4%) the module's own runner uses
        ebitda_cagr=s.get("cagr", rollup.DEFAULT_EBITDA_CAGR),
        hold_years=s.get("hold", hold))
        for s in base_family(family)}
    observed_best = max(b["moc"] for b in base.values())

    rng = np.random.default_rng(seed)
    n_scen = len(family)
    # per-draw, per-scenario null MOC: growth & exit-delta ~ N(0, sigma)
    g = rng.normal(0.0, sigma_growth, size=(n, n_scen))
    d = rng.normal(0.0, sigma_exit_delta, size=(n, n_scen))
    mocs = np.empty_like(g)
    for i, s in enumerate(family):
        for j in range(n):
            mocs[j, i] = irr_waterfall.equity_multiple_bridge(
                entry_multiple=s["entry"],
                exit_multiple=float(s["entry"] + d[j, i]),
                leverage=lev, ebitda_cagr=float(g[j, i]), hold_years=hold)["moc"]
    best_of_family = mocs.max(axis=1)
    mass = float((best_of_family >= observed_best - 1e-9).mean())
    return {
        "n": int(n),
        "seed": int(seed),
        "family_size": int(n_scen),
        "sigma_growth": sigma_growth,
        "sigma_exit_delta": sigma_exit_delta,
        "observed_best_moc": round(float(observed_best), 4),
        "null_mean_best_of_family": round(float(best_of_family.mean()), 4),
        "prior_predictive_mass": mass,
        "deflated_survives_at_10pct": bool(mass < 0.10),
        "note": ("mass = P(best-of-M MOC >= observed best | zero-edge null "
                 "with realistic committee uncertainty); small mass = the "
                 "expansion MOC is not input luck"),
    }


def base_family(family: Sequence[Dict[str, float]]) -> List[Dict[str, float]]:
    """Normalize the scenario family to dicts the bridge accepts."""
    if family is None:
        return list(irr_waterfall.DEFAULT_SCENARIOS)
    return [dict(s) for s in family]
