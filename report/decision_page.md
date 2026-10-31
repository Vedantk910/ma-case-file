# M&A Decision Page — 12-Deal Buy / Build / Partner
*One page. 12 EDGAR-sourced deals, 2015–2025. Every figure reproducible via
`python -m notebooks.run_notebook` (offline, cache-first, writes
`out/decision_numbers.json`).*

## The one-liner
**Buy at ≤ 9x with ≥ 50% synergy capture; above that, the cheaper alternative is
build (e-commerce) or partner (logistics).** The entry multiple is the decision
pivot: it alone separates the accretive region from the dilutive one, and the
synergy capture rate is the largest secondary lever next to it.

## 1. The decision boundary (accretion zero-line)
The accretion model is linear in the entry multiple, so the point where year-1
EPS effect = 0 has a closed form (pinned to the numeric solver to 1e-4):

| Synergy capture | 0% | 25% | 50% | 75% | 100% |
|---|---|---|---|---|---|
| **Zero-line (buy-only below)** | 10.0x | 11.7x | 13.3x | 15.0x | 16.7x |

Buy *only* below this line. At no capture is 12x accretive; at full capture the
zone stretches to ~17x. The zero-line **rises with capture** — synergies you can
actually contract for buy you a wider zone. (Case file: break-even ≈ 8–9x at
mid-capture.)

## 2. Synergy decay: "accretive for N years, then inverts"
The stated synergy is a run-rate that erodes (full Y1 → 40–60% by Y5,
literature-typical for logistics; [unverified] the floor is a committee input).
Year-by-year EPS at two prices (default floor 0.5):

| Price | Y1 | Y2 | Y3 | Y4 | Y5 | Accretive years |
|---|---|---|---|---|---|---|
| 8x | +2.6% | +2.35% | +2.1% | +1.85% | +1.6% | **5 of 5** |
| 14x | +0.8% | +0.55% | +0.3% | +0.05% | −0.2% | **4 of 5, then inverts** |

The number a buy-vs-build decision needs is not "accretive in year one" but
**how long** the deal stays accretive before the decay inverts it.

## 3. Per-deal IRR waterfalls (gate split, sector-matched)
Sponsor IRR at 4x leverage, 5-yr hold, decomposed so the reader sees which gate
is doing the work — the distribution, not just the estimate:

| Scenario | E-commerce IRR | Logistics IRR | Where the value comes from |
|---|---|---|---|
| 6x in → 12x out (expansion) | **41.4%** | 37.7% | 82% multiple-expansion gate |
| 8x in → 8x out (growth only) | 9.2% | 5.7% | 100% EBITDA-growth gate |
| 12x in → 6x out (mean-rev) | **−14.5%** | −18.1% | negative multiple gate |

Two defensible findings: (i) **the IRR is a multiple assumption, not a business
return** — the expansion case is 82% a multiple-expansion bet; strip the
assumption (growth-only) and the edge is a thin 5–9%. (ii) **scale invariance**
— a $16B and a $0.33B deal at the same multiples print the same IRR; deal size
sets *capacity*, not return. That is why per-deal IRR differences come from
sector growth, never headline value.

## 4. The buy / build / partner trigger (the new page)
Three strategies priced on **one yardstick** (target-EBITDA units, so the
comparison is scale-invariant) against the case file's *sourced* value anchor —
the intrinsic DCF multiple (19.8x at 8% WACC, falling to 11.4x at 12%). Net PV
at 8x entry, 50% capture (e-commerce shown; logistics has the higher build capex):

| Strategy | What it is | Net PV | Trigger |
|---|---|---|---|
| **Buy** | full value + decaying synergy − price | **120.9** | ≤ 12.0x |
| Build | 85% of value, synergy at 60% haircut, in-house capex | 80.0 | above the buy cap |
| Partner | 70% of value, no target synergy, rate card | 38.8 | the low-commitment floor |

The trigger is the **buy price cap** — the entry multiple at which the cheaper
alternative overtakes buy:

- **E-commerce deals:** BUY at ≤ **12.0x** (cap set by in-house build CAPEX);
  above that, **build** is cheaper.
- **Logistics deals:** BUY at ≤ **16.0x** (network capex is expensive to
  replicate, so buy stays ahead longer); above that, **partner** is cheaper.

Same entry multiple, different sectors → different caps. That sector split, not
the deal name, is what the page differentiates.

## What we would ask the client (carried from the case file)
1. **Entry-multiple ceiling** — at what EV/EBITDA does the committee stop being
   accretive even at 100% capture; is that a tolerance or a hard cap?
2. **Synergy contractability** — what share of stated synergy is held to a
   contractual / 8-K-committed basis in year 1, and who signs it?
3. **The build & partner cost proxies** — the in-house CAPEX and rate-card
   numbers above are committee inputs, not sourced constants; what does the
   client's ops team actually quote?
4. **Discount-rate policy** — what WACC band is the committee's, and can the
   terminal value be de-weighted so the multiple, not the rate, drives the range?
5. **Leverage & IRR hurdle** — at 3x/4x/5x leverage, does the roll-up clear the
   target IRR on a *flat* multiple, or only on a rising one?

## Honest limits
- The **buy / build / partner cost proxies** (in-house CAPEX, rate cards, the
  85%/70% value shares) are committee inputs, tagged `[unverified]`; the
  defensible part is that all three are priced on one yardstick against a
  *sourced* value anchor.
- The **synergy-decay floor** (40–60% by Y5) is literature-typical, not a
  sourced constant; the direction is consensus, the exact floor is the client's.
- **No deal in the book has a clean public EBITDA multiple** — the multiples
  here are the *decision inputs*, not historical deal values. The announced value
  sets capacity, not return (the IRR scale-invariance result).

## CV bullet
> M&A decision tool on 12 EDGAR-sourced deals: accretion decision surfaces with
> the synergy-decay "accretive-for-N-years" boundary and per-deal IRR
> waterfalls (gate-split, sector-matched); quantified buy/build/partner
> triggers — 9x full-capture break-even, e-com buy-cap 12x vs logistics 16x.
