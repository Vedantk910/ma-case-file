# ma-case-file

M&A screening told like a case file: twelve public e-commerce and logistics
acquisitions, swept across entry-multiple and synergy-capture grids, with a DCF
discount-rate sensitivity band and a roll-up IRR matrix.

**C1 flagship — the M&A Decision Tool.** The three screens above become a
*decision*: a synergy-decay "accretive-for-N-years" boundary, an accretion
zero-line ("buy only here"), per-deal IRR waterfalls with a gate split, and a
buy / build / partner trigger line for every deal in the book. That decision
page — not the case file — is what separates a screening deck from a tool a
client can act on.

## The honest numbers

Case file (baseline):
- +3.2% first-year EPS accretion at a 6x entry multiple with full synergy capture.
- Above roughly 9x entry, every deal in the set is dilutive in year one.
- Synergy capture is worth up to two EPS points; the break-even band sits near 9x.

Decision tool (new):
- **Zero-line:** the buy-only boundary runs 10x (no synergy) to 16.7x (full
  synergy); the 8–9x break-even band sits in the middle of that surface.
- **Synergy decay:** at 8x a deal stays accretive all five years; at 14x it is
  accretive four of five and inverts in year 5. The decision input is *how
  long*, not just *whether*.
- **IRR waterfalls:** the expansion case (6x in / 12x out) is ~41% e-commerce
  IRR but 82% of the value is a multiple-expansion assumption, not a business
  return; growth-only (8x/8x) is a thin 9%. IRR is scale-invariant — deal size
  sets capacity, not return.
- **Buy/build/partner:** at 8x entry, buy nets 120.9 vs build 80.0 vs partner
  38.8 (e-commerce, 50% capture). The trigger is the buy price cap — 12.0x for
  e-commerce, 16.0x for logistics — set by the cheaper alternative, not a gut
  call.

## What it does

1. **Data** — twelve public deals (2015–2025) with deal and target
   fundamentals from SEC EDGAR, plus a cached fact sheet per name
2. **Model** — an EPS accretion grid across entry multiple and synergy capture
   (`model/accretive.py`), a DCF discount-rate sensitivity band, and a roll-up
   IRR matrix
3. **Decision** — the `decision/` package:
   - `synergy_decay.py` — realized synergies erode Y1→Y5; "accretive for N
     years, then inverts"
   - `surfaces.py` — the entry × capture × WACC decision volume, with the
     accretion zero-line as the buy-only boundary
   - `irr_waterfall.py` — a per-deal, gate-by-gate IRR bridge (equity in →
     growth → multiple expansion → sponsor value)
   - `decision_page.py` — the buy / build / partner trigger engine
4. **Output** — a one-page case file (`report/case_file.md`) *and* a one-page
   decision page (`report/decision_page.md`) a partner would screenshot

## Project layout

```
data/       # deal set + EDGAR sanity checks, cached facts
model/      # accretive.py, sensitivity.py, rollup.py
decision/   # synergy_decay, surfaces, irr_waterfall, decision_page
notebooks/  # model_full.ipynb + runner (one-command end-to-end, writes out/)
report/     # case_file.md + decision_page.md
tests/      # pytest suite (offline; 38 cases incl. the decision tool)
```

## Quick start

```bash
pip install -r requirements.txt
python -m notebooks.run_notebook   # end-to-end, writes out/decision_numbers.json
python -m pytest tests/ -q         # 38 offline tests
```

The break-even maths is the deliverable: it states the entry price at which the
transaction stops working, reports the dilutive region rather than burying it,
and — in the decision tool — says *what to do* (buy / build / partner) with a
number you can re-run.

## 7-gate trail (C1 decision tool)

- **G0 scope** — one decision: which of the 12 deals do we buy, which do we
  build, which do we partner into?
- **G1 build** — four `decision/` modules extending the three screens; seeded,
  cache-first, offline.
- **G2 test** — 29 new offline tests (38 total); each module has a
  closed-form-vs-numeric pin, a scale-invariance check, and a decay-consistency
  check.
- **G3 verify** — `python -m notebooks.run_notebook` regenerates
  `out/decision_numbers.json` with every quoted number; the EDGAR section reads
  the JSON cache.
- **G4 stress/ablation** — dropping synergy capture to 0 collapses the buy zone
  to a single multiple; the duration/build cost proxy is the whole e-com vs
  logistics difference, so ablation *is* the sector split.
- **G5 document** — this README + `report/decision_page.md` with the honest
  limits (cost proxies and decay floor tagged `[unverified]`).
- **G6 hostile pass** — the three attacks and the answers:

| Attack | Answer |
|---|---|
| "Your screen uses multiples that don't exist publicly — defend the decision inputs." | The multiples are *decision inputs*, not historical values: none of the 12 deals discloses a clean EBITDA multiple, so the screen supplies its own and the value sets capacity, not return (scale-invariance proved in the IRR waterfall). |
| "Is the IRR a real return or a multiple assumption?" | The waterfall decomposes it: 82% of the expansion case is the multiple gate; strip it (growth-only) and the edge is 9%. The distribution is reported, not just the point. |
| "How do you know when to stop buying?" | The synergy-decay boundary: a deal is "accretive for N years, then inverts" (5 of 5 at 8x, 4 of 5 at 14x, 0 at 18x). The buy price cap is the point where the cheaper alternative overtakes — 12x e-com, 16x logistics. |

What I would change next: a sourced in-house build / partner cost model (the
current proxies are committee inputs), an 8-K-committed synergy schedule per
deal, and a live DCF per deal instead of the shared intrinsic anchor.
