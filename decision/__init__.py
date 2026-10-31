"""M&A Decision Tool (project P3 -> consulting flagship C1).

The case file's three screens (accretion / DCF / LBO IRR) become a *decision*
here. Four self-contained modules, all numpy/pandas only, all offline:

  - synergy_decay  : realized synergies ramp and erode over Y1..Y5, so a deal
                     is accretive for N years, then inverts.
  - surfaces       : the entry-multiple x synergy-capture x discount-rate
                     decision surface, with the accretion zero-line ("buy only
                     here") as the boundary.
  - irr_waterfall  : a per-scenario IRR waterfall (equity in -> growth ->
                     multiple expansion -> sponsor value) on the LBO engine.
  - decision_page  : the buy / build / partner trigger engine; one line per
                     deal with a quantified, testable trigger.

The decision page is the artifact that separates a case file from a decision
tool: it tells the client which deal to buy, which to partner into, and which
to build in-house, each with a number they can defend.
"""
from . import synergy_decay, surfaces, irr_waterfall, decision_page
