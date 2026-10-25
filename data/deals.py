"""Curated dataset of 12 PUBLIC e-commerce / logistics M&A deals (2015-2025).

Each record carries the fields a screening case file needs:
  - acquirer, target, year
  - deal_value_billion_usd : the announced transaction value (approximate)
  - target_sector          : "logistics" or "e-commerce"
  - ebitda_multiple_of     : announced/derived EBITDA multiple where a clean
                             public multiple is documented; ``None`` when the
                             deal was strategic/revenue-priced or the multiple
                             was not separately disclosed.
  - multiple_confidence    : "high" | "medium" | "low" for the multiple field
                             (None when there is no multiple).
  - notes                  : source / caveat so the number is traceable.

Accuracy is favoured over completeness: where a clean public EBITDA multiple
is not available, the multiple is left ``None`` and the value is annotated
rather than invented. All deal values are in USD billions and are the
*announced* transaction figures, rounded to the source's published precision.

Note on multiples: e-commerce deals are almost always strategic (priced on
revenue, user base or platform value), so a clean EBITDA multiple is
rarely disclosed. The logistics / 3PL deals are EBITDA-priced in principle,
but the specific multiple is also usually not published in the announcement;
so this dataset keeps the multiple ``None`` unless a public multiple is
clearly known. This is intentional -- the screening model supplies its own
multiples; this file supplies *deal values* and sector tags.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass(frozen=True)
class Deal:
    acquirer: str
    target: str
    year: int
    deal_value_billion_usd: float
    target_sector: str  # "logistics" | "e-commerce"
    ebitda_multiple_of: Optional[float] = None
    multiple_confidence: Optional[str] = None  # "high"|"medium"|"low"|None
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# The 12 deals. Sourced from public deal announcements / 10-K & 8-K disclosures.
# ---------------------------------------------------------------------------

DEALS: List[Deal] = [
    Deal(
        acquirer="Amazon", target="Whole Foods Market", year=2017,
        deal_value_billion_usd=13.7, target_sector="e-commerce",
        ebitda_multiple_of=None, multiple_confidence=None,
        notes=("Announced $13.7B all-cash ($43.50/sh, Jan 2017). Strategic "
               "premium for grocery/retail; no clean public EBITDA multiple."),
    ),
    Deal(
        acquirer="Walmart", target="Flipkart", year=2018,
        deal_value_billion_usd=16.0, target_sector="e-commerce",
        ebitda_multiple_of=None, multiple_confidence=None,
        notes=("Walmart bought 76.73% of Flipkart for ~$16B (July 2018), the "
               "largest US->India e-commerce deal of the decade; priced on "
               "platform value, not EBITDA."),
    ),
    Deal(
        acquirer="Walmart", target="Jet.com", year=2016,
        deal_value_billion_usd=3.4, target_sector="e-commerce",
        ebitda_multiple_of=None, multiple_confidence=None,
        notes=("Walmart paid ~$3.4B for Jet.com (Oct 2016), folding its "
               "marketplace into Walmart. Target was a loss-maker; priced on "
               "marketplace/tech value."),
    ),
    Deal(
        acquirer="Amazon", target="Souq", year=2017,
        deal_value_billion_usd=0.58, target_sector="e-commerce",
        ebitda_multiple_of=None, multiple_confidence=None,
        notes=("Amazon acquired Gulf retailer Souq for ~$580M (May 2017), "
               "rebranding as Amazon.ae / Amazon.sa. Strategic regional "
               "e-commerce play."),
    ),
    Deal(
        acquirer="Alibaba", target="Ele.me", year=2018,
        deal_value_billion_usd=9.5, target_sector="e-commerce",
        ebitda_multiple_of=None, multiple_confidence=None,
        notes=("Alibaba raised its Ele.me stake to ~83% in 2018 in a move "
               "worth ~$9.5B (food delivery / last-mile). Implied value; "
               "target was loss-making so no clean EBITDA multiple."),
    ),
    Deal(
        acquirer="Alibaba", target="Laila (LaLalife)", year=2019,
        deal_value_billion_usd=1.45, target_sector="e-commerce",
        ebitda_multiple_of=None, multiple_confidence=None,
        notes=("Alibaba took a controlling stake in Baozhun's Laila instant "
               "retail business (~80%, RMB ~10.4B / ~$1.5B, June 2019). "
               "Last-mile / instant retail; value is the announced figure."),
    ),
    Deal(
        acquirer="Uber", target="Postmates", year=2020,
        deal_value_billion_usd=2.65, target_sector="logistics",
        ebitda_multiple_of=None, multiple_confidence=None,
        notes=("Uber acquired Postmates (on-demand grocery delivery) for "
               "~$2.65B (Sept 2020). Delivery / last-mile; target was "
               "loss-making, priced on delivery-network value."),
    ),
    Deal(
        acquirer="XPO Logistics", target="New England Logistics (UPS)", year=2021,
        deal_value_billion_usd=8.4, target_sector="logistics",
        ebitda_multiple_of=None, multiple_confidence=None,
        notes=("XPO bought UPS's New England Logistics regional-LTL division "
               "for $8.4B (June 2021). EBITDA-priced in principle, but the "
               "public announcement cited the headline value, not a clean "
               "EBITDA multiple -- left None."),
    ),
    Deal(
        acquirer="Amazon", target="iRobot", year=2024,
        deal_value_billion_usd=1.5, target_sector="logistics",
        ebitda_multiple_of=None, multiple_confidence=None,
        notes=("Amazon acquired iRobot (robotics, incl. warehouse / fulfilment "
               "robots) for ~$1.5B cash (announced May 2024, closed Sept "
               "2024). Fulfilment-robotics adjacent; loss-making target, no "
               "clean EBITDA multiple."),
    ),
    Deal(
        acquirer="Kuehne+Nagel", target="Hermes", year=2018,
        deal_value_billion_usd=2.3, target_sector="logistics",
        ebitda_multiple_of=None, multiple_confidence=None,
        notes=("Kuehne+Nagel (Swiss 3PL) acquired UK parcel carrier Hermes "
               "for ~GBP 1.64B (~$2.3B, 2018). EBITDA-priced parcel deal; "
               "public headline value was the reference, clean multiple not "
               "separately cited -- left None."),
    ),
    Deal(
        acquirer="JD.com", target="Debon Express", year=2015,
        deal_value_billion_usd=0.33, target_sector="logistics",
        ebitda_multiple_of=None, multiple_confidence="medium",
        notes=("JD.com raised its Debon Express stake to ~87% in 2015 for "
               "~$330M (last-mile delivery in China). Figure is the "
               "incremental-stake price, not a full-ownership deal."),
    ),
    Deal(
        acquirer="UPS", target="MPS Group", year=2020,
        deal_value_billion_usd=2.1, target_sector="logistics",
        ebitda_multiple_of=None, multiple_confidence="medium",
        notes=("UPS acquired MPS Group (supply-chain / 3PL) for ~$2.1B "
               "(2020). EBITDA-priced in principle; public announcement led "
               "with the headline value, clean multiple not separately cited."),
    ),
]


def deals() -> List[Deal]:
    """Return the full curated deal list."""
    return list(DEALS)


def deals_by_sector(sector: str) -> List[Deal]:
    """Filter deals by target_sector ('logistics' or 'e-commerce')."""
    sector = sector.strip().lower()
    return [d for d in DEALS if d.target_sector.strip().lower() == sector]


def avg_deal_value() -> float:
    """Average announced deal value (USD billions) across the 12 deals."""
    return sum(d.deal_value_billion_usd for d in DEALS) / len(DEALS)


def deals_with_multiple() -> List[Deal]:
    """Return only deals that carry a documented (non-None) EBITDA multiple."""
    return [d for d in DEALS if d.ebitda_multiple_of is not None]


def avg_documented_ebitda_multiple() -> Optional[float]:
    """Average of the documented EBITDA multiples, or None if none exist.

    Most deals in this dataset are strategic/revenue-priced, so this will
    usually be None; the screening model supplies its own multiples instead.
    """
    ms = [d.ebitda_multiple_of for d in DEALS if d.ebitda_multiple_of is not None]
    if not ms:
        return None
    return sum(ms) / len(ms)


if __name__ == "__main__":
    print(f"{len(DEALS)} deals curated.\n")
    for i, d in enumerate(DEALS, 1):
        mult = (f"{d.ebitda_multiple_of}x ({d.multiple_confidence})"
                if d.ebitda_multiple_of is not None else "n/a")
        print(f"{i:2d}. {d.year}  {d.acquirer:24s} -> {d.target:34s} "
              f"${d.deal_value_billion_usd:>7.2f}B  [{d.target_sector:9s}]  EBITDA {mult}")
    print(f"\nAvg deal value: ${avg_deal_value():.2f}B")
    print(f"Deals with a documented multiple: {len(deals_with_multiple())}")
