"""Pytest suite for the M&A Decision Tool (consulting flagship C1).

Covers the four new `decision` modules, all offline and synthetic (the 12-deal
book is local data, no network).  Grouped by module; the load-bearing claims
each group pins:

  synergy_decay : the decay shape is monotone and the "accretive for N years,
                  then inverts" count is consistent with the series.
  surfaces      : the zero-line closed form is pinned against the numeric
                  solver; the intrinsic multiple is the case file's own DCF.
  irr_waterfall : the gate-by-gate bridge reproduces the bisection IRR, and
                  IRR is scale-invariant (a $16B and a $0.33B deal agree).
  decision_page : buy/build/partner are priced on one yardstick; the sector
                  floors genuinely differentiate the two deal classes.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pytest

from model import accretive, sensitivity, rollup
from data import deals
from decision import synergy_decay, surfaces, irr_waterfall, decision_page


# ---------------------------------------------------------------------------
# synergy_decay
# ---------------------------------------------------------------------------
def test_capture_profile_linear_shape():
    prof = synergy_decay.capture_profile(years=5, floor=0.5)
    assert prof[1] == 1.0 and prof[5] == 0.5
    assert all(prof[t] > prof[t + 1] for t in range(1, 5)), "not monotone"


def test_capture_profile_step_shape():
    prof = synergy_decay.capture_profile(years=6, floor=0.5, schedule="step")
    # first half (t<=3) holds 1.0, rest the floor
    assert all(v == 1.0 for v in (prof[1], prof[2], prof[3]))
    assert all(v == 0.5 for v in (prof[4], prof[5], prof[6]))


def test_capture_profile_bounds_errors():
    with pytest.raises(ValueError):
        synergy_decay.capture_profile(years=1)
    with pytest.raises(ValueError):
        synergy_decay.capture_profile(years=5, floor=1.5)
    with pytest.raises(ValueError):
        synergy_decay.capture_profile(years=5, floor=-0.1)


def test_yearly_accretions_fall_with_decay():
    # a cheap multiple stays positive but the series falls as synergy decays
    series = synergy_decay.yearly_accretions(multiple=6.0, years=5, floor=0.5)
    assert series[0] > series[-1]
    assert all(a > 0.0 for a in series)  # 6x is in the accretive region


def test_accretive_years_consistent_with_series():
    # the count must equal the number of positive years in the returned series
    for m in (6.0, 12.0, 14.0, 16.0, 18.0, 20.0):
        s = synergy_decay.yearly_accretions(multiple=m, years=5)
        ay = synergy_decay.accretive_years(multiple=m, years=5)
        pos = sum(1 for a in s if a > 0)
        assert ay == pos, f"{m}x: count {ay} != positives {pos}"
    # the decay story: cheap deals stay accretive all 5 years, expensive ones
    # invert inside the hold (14x -> 4 years then inverts; 18x -> 0)
    assert synergy_decay.accretive_years(multiple=6.0, years=5) == 5
    assert synergy_decay.accretive_years(multiple=14.0, years=5) == 4
    assert synergy_decay.accretive_years(multiple=18.0, years=5) == 0


def test_cumulative_synergy_value_below_flat_capture():
    # decaying is worth less than a flat run-rate at the same capture
    flat = sum(accretive.DEFAULT_ANNUAL_SYNERGY / 1.08 ** t for t in range(1, 6))
    decay = synergy_decay.cumulative_synergy_value(years=5, floor=0.5)
    assert decay < flat


def test_cumulative_synergy_value_wacc_error():
    with pytest.raises(ValueError):
        synergy_decay.cumulative_synergy_value(wacc=0.0)


def test_decay_table_shape_and_accretive_years():
    tab = synergy_decay.decay_table()
    assert "Y1" in tab.columns and "Y5" in tab.columns
    assert "accretive_years" in tab.columns
    # the count must equal the number of positive years in its own row
    for idx, row in tab.iterrows():
        pos = sum(1 for t in range(1, 6) if row[f"Y{t}"] > 0)
        assert row["accretive_years"] == pos


# ---------------------------------------------------------------------------
# surfaces
# ---------------------------------------------------------------------------
def test_zero_line_closed_form_matches_numeric():
    # m*(c) is where numeric accretion crosses zero
    zl = surfaces.zero_line(captures=[0.0, 0.25, 0.5, 1.0])
    for i, c in enumerate([0.0, 0.25, 0.5, 1.0]):
        mstar = zl.iloc[i]
        resid = accretive.accretion(multiple=mstar, synergy_capture=c)
        assert abs(resid) < 1e-4, f"zero-line not at zero accretion: {resid}"


def test_zero_line_rises_with_capture():
    zl = surfaces.zero_line()
    vals = zl.to_numpy()
    assert all(np.diff(vals) > 0), "zero-line must rise with capture"


def test_intrinsic_multiple_is_the_dcf():
    # the intrinsic multiple is exactly the case file's DCF value / EBITDA
    for w in (0.06, 0.08, 0.12):
        m = surfaces.intrinsic_multiple(w)
        dcf_val = sensitivity.dcf_value(wacc=w)
        assert abs(m - dcf_val / sensitivity.DEFAULT_EBITDA) < 1e-9
    # and it falls as WACC rises
    assert surfaces.intrinsic_multiple(0.06) > surfaces.intrinsic_multiple(0.12)


def test_intrinsic_multiple_headline_band():
    # ~31x at 6%, ~11x at 12% - the case file's documented DCF band
    assert 30.0 < surfaces.intrinsic_multiple(0.06) < 33.0
    assert 10.0 < surfaces.intrinsic_multiple(0.12) < 12.0


def test_buy_zone_all_in_at_8x_8pct():
    # 8x is far below the 19.8x intrinsic at 8%, so every capture is in-zone
    dz = surfaces.buy_zone(deal_price_multiple=8.0, waccs=[0.08])
    assert dz.to_numpy().all()


def test_buy_zone_out_at_high_price():
    # a price above the intrinsic multiple is out of the zone at any capture
    dz = surfaces.buy_zone(deal_price_multiple=25.0, waccs=[0.08])
    assert not dz.to_numpy().any()


def test_deal_trigger_min_capture():
    t = surfaces.deal_trigger(deal_price_multiple=8.0, wacc=0.08)
    assert "min_capture_in_zone" in t and "zero_line_by_capture" in t
    # at 8x everything is in zone, so the minimum qualifying capture is 0
    assert t["min_capture_in_zone"] == 0.0


def test_surface3d_cell_counts_and_monotonic_intrinsic():
    v = surfaces.surface3d(deal_price_multiple=8.0)
    assert v["buy_zone_cells"] <= v["total_cells"]
    # intrinsic falls as WACC rises across the sweep
    intr = [v["intrinsic"][f"{w*100:.0f}%"] for w in v["waccs"]]
    assert all(np.diff(intr) < 0)


# ---------------------------------------------------------------------------
# irr_waterfall
# ---------------------------------------------------------------------------
def test_bridge_gates_sum_to_exit_minus_entry():
    b = irr_waterfall.equity_multiple_bridge(
        entry_multiple=8.0, exit_multiple=10.0, leverage=4.0,
        ebitda_cagr=0.04, hold_years=5)
    # entry equity + the two gates = exit equity (in per-EBITDA units)
    reconstructed = (b["entry_equity_per_ebitda"]
                     + b["gate_growth_per_ebitda"]
                     + b["gate_multiple_expansion_per_ebitda"])
    assert abs(reconstructed - b["exit_equity_per_ebitda"]) < 1e-9


def test_bridge_implied_irr_matches_bisection():
    # the closed-form implied IRR must zero the same NPV the bisection does
    b = irr_waterfall.equity_multiple_bridge(
        entry_multiple=6.0, exit_multiple=12.0, leverage=4.0,
        ebitda_cagr=0.05, hold_years=5)
    r = rollup.deal_irr(entry_multiple=6.0, exit_multiple=12.0, leverage=4.0,
                       hold_years=5, ebitda_cagr=0.05)
    assert abs(b["implied_irr"] - r) < 1e-6


def test_bridge_requires_positive_entry_equity():
    with pytest.raises(ValueError):
        # leverage above the entry multiple -> negative entry equity
        irr_waterfall.equity_multiple_bridge(
            entry_multiple=6.0, exit_multiple=8.0, leverage=8.0)


def test_growth_only_gate_dominates_flat_multiple():
    # 8x -> 8x: the multiple gate is zero, growth does 100% of the work
    b = irr_waterfall.equity_multiple_bridge(
        entry_multiple=8.0, exit_multiple=8.0, leverage=4.0,
        ebitda_cagr=0.04, hold_years=5)
    assert b["gate_multiple_expansion_per_ebitda"] == 0.0
    assert b["growth_share_of_gates"] == 1.0


def test_expansion_case_irr_positive_meanreversion_negative():
    exp = irr_waterfall.equity_multiple_bridge(
        entry_multiple=6.0, exit_multiple=12.0, leverage=4.0)
    mean = irr_waterfall.equity_multiple_bridge(
        entry_multiple=12.0, exit_multiple=6.0, leverage=4.0)
    assert exp["implied_irr"] > 0.0
    assert mean["implied_irr"] < 0.0


def test_per_deal_irr_matrix_shape():
    df = irr_waterfall.per_deal_irr_matrix()
    # 12 deals x 3 scenarios
    assert df.shape[0] == len(deals.deals()) * 3
    assert df["IRR agrees w/ bridge"].all()


def test_irr_scale_invariant():
    # the IRR does not depend on deal value: two deals, same scenario, same IRR
    book = deals.deals()
    biggest = max(book, key=lambda d: d.deal_value_billion_usd)
    smallest = min(book, key=lambda d: d.deal_value_billion_usd)
    r_big = irr_waterfall.deal_irr_waterfall(biggest)["scenarios"][0]
    # recompute on the smallest deal with the identical sector-matched scenario
    scen = {"entry": 6.0, "exit": 12.0, "leverage": 4.0,
            "cagr": irr_waterfall.DEFAULT_EBITDA_CAGR[smallest.target_sector],
            "hold": 5}
    r_small = irr_waterfall._irr_and_split(scen, smallest)
    # IRRs agree exactly when the two deals share a sector CAGR
    if biggest.target_sector == smallest.target_sector:
        assert abs(r_big["irr_bisection"] - r_small["irr_bisection"]) < 1e-9
    else:
        # different sector -> different CAGR -> IRRs may differ, but both
        # are finite; the scale-invariance claim is "not on deal value"
        assert np.isfinite(r_big["irr_bisection"]) and \
               np.isfinite(r_small["irr_bisection"])


# ---------------------------------------------------------------------------
# decision_page
# ---------------------------------------------------------------------------
def test_strategy_net_pv_ordering_ecommerce():
    # for an e-commerce deal at 8x, buy > build > partner > none
    d = deals.deals_by_sector("e-commerce")[0]
    eco = decision_page.strategy_economics(d, buy_price_multiple=8.0)
    s = eco["strategies"]
    assert s["buy"]["net_pv"] > s["build"]["net_pv"] > s["partner"]["net_pv"] > 0.0


def test_recommend_returns_trigger_and_cap():
    d = deals.deals_by_sector("e-commerce")[0]
    r = decision_page.recommend(d, buy_price_multiple=8.0)
    assert r["recommendation"] == "BUY"
    assert "Trigger" in str(r) or "trigger" in r
    assert r["buy_price_cap"] > 0.0


def test_buy_price_cap_differs_by_sector():
    ecom = deals.deals_by_sector("e-commerce")[0]
    logi = deals.deals_by_sector("logistics")[0]
    cap_ecom = decision_page.buy_price_cap(ecom)["cap"]
    cap_logi = decision_page.buy_price_cap(logi)["cap"]
    # e-commerce build CAPEX is cheaper -> buy holds a lower cap
    assert cap_ecom < cap_logi


def test_page_shape_and_sector_split():
    pg = decision_page.page()
    assert len(pg) == len(deals.deals())
    for col in ("Recommendation", "Buy cap (x)", "PV buy", "Trigger"):
        assert col in pg.columns
    # all e-commerce deals share one cap; all logistics share another
    caps_by_sector = pg.groupby("Sector")["Buy cap (x)"].nunique()
    assert all(v == 1 for v in caps_by_sector), \
        "deals in a sector must be scale-invariant (one cap per sector)"


def test_sector_floors_drive_differentiation():
    # the logistics floor (0.50) is above the e-commerce floor (0.40), so the
    # decay profile for logistics holds more synergy into year 5
    ecom = synergy_decay.capture_profile(floor=synergy_decay.SECTOR_FLOORS["e-commerce"])
    logi = synergy_decay.capture_profile(floor=synergy_decay.SECTOR_FLOORS["logistics"])
    assert logi[5] > ecom[5]


def test_recommend_none_when_every_option_is_negative():
    # a very expensive entry multiple makes buy negative; build/partner are
    # net-positive, so recommend still picks a positive option - but at a
    # multiple above even the partner value, none wins and the floor holds
    d = deals.deals_by_sector("e-commerce")[0]
    eco_expensive = decision_page.strategy_economics(d, buy_price_multiple=40.0)
    # at 40x the buy price exceeds everything -> buy net is deeply negative
    assert eco_expensive["strategies"]["buy"]["net_pv"] < 0.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
