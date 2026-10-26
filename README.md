# ma-case-file

M&A screening told like a case file: twelve public e-commerce and logistics acquisitions, swept across entry-multiple and synergy-capture grids, with a DCF discount-rate sensitivity band and a roll-up IRR matrix.

## The honest numbers

- +3.2% first-year EPS accretion at a 6x entry multiple with full synergy capture.
- Above roughly 9x entry, every deal in the set is dilutive in year one.
- Synergy capture is worth up to two EPS points; the break-even band sits near 9x.

## What it does

1. **Data** — twelve public deals (2015–2025) with deal and target fundamentals from SEC EDGAR, plus a cached fact sheet per name
2. **Model** — an EPS accretion grid across entry multiple and synergy capture (`model/accretive.py`), a DCF discount-rate sensitivity band, and a roll-up IRR matrix
3. **Output** — a one-page case file (`report/case_file.md`) a partner would screenshot

## Project layout

```
data/     # deal set + EDGAR sanity checks, cached facts
model/    # accretive.py, sensitivity.py, rollup.py
notebooks/ # model_full.ipynb + runner
report/   # case_file.md
tests/    # pytest suite (offline)
```

## Quick start

```bash
pip install -r requirements.txt
python -m notebooks.run_notebook   # end-to-end
python -m pytest tests/ -q
```

The break-even maths is the deliverable: it states the entry price at which the transaction stops working, and reports the dilutive region rather than burying it.
