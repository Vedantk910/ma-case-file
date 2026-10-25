"""EDGAR EBITDA / revenue sanity checks with an on-disk cache (project P3).

Pulls TTM revenue and net income for a handful of *acquirer/target* public
issuers using the `edgar` library (SEC EDGAR API), and writes each pull to
JSON in ``cache/`` so repeated notebook runs do not re-hit the SEC API.

This is deliberately defensive: the deal dataset in ``data/deals.py`` keeps
deal values from public announcements; the EDGAR pull is only a *sanity
check* that an acquirer's own reported revenue/net-income scale is consistent
with the screen's order-of-magnitude assumptions.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional

# Where the JSON cache lives, next to the rest of the project.
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"


def _cache_path(ticker: str) -> Path:
    safe = ticker.strip().upper().replace("/", "-")
    return CACHE_DIR / f"{safe}_facts.json"


def _extract_value(metric: object) -> Optional[float]:
    """Pull the numeric value out of whatever shape the edgar lib returns.

    The library returns a ``TTMMetric`` (dataclass-ish); the number may live
    under ``.value``, ``.amount`` or as the first positional field.
    """
    for attr in ("value", "amount"):
        if hasattr(metric, attr):
            v = getattr(metric, attr)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
    # fall back to dataclass fields, first one that is numeric
    fields = getattr(metric, "__dataclass_fields__", None)
    if fields:
        for name in fields:
            v = getattr(metric, name, None)
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def fetch_company_facts(
    ticker: str,
    use_cache: bool = True,
    timeout: int = 30,
) -> Dict[str, Optional[float]]:
    """Return {'revenue': x, 'net_income': y, 'source': ...} for a ticker.

    - Reads ``cache/<TICKER>_facts.json`` first when ``use_cache`` and the
      file exists.
    - Otherwise hits EDGAR via the `edgar` library and writes the cache.
    - Never raises on a pull failure: returns the cache, or a dict with
      ``None`` values and ``'source': 'error'`` so the notebook can render
      it gracefully.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = _cache_path(ticker)
    if use_cache and cache.exists():
        try:
            return json.loads(cache.read_text())
        except json.JSONDecodeError:
            pass  # fall through to a fresh pull

    out: Dict[str, Optional[float]] = {
        "ticker": ticker.upper(),
        "revenue": None,
        "net_income": None,
        "source": None,
        "pulled_at": time.time(),
    }

    try:
        import os
        import edgar  # local import so the module loads even if edgar is gone

        # SEC requires a descriptive User-Agent identifying the requester.
        # Honour EDGAR_IDENTITY if the user set it; else use a default that
        # still satisfies the "non-default, identifying" requirement.
        identity = os.environ.get("EDGAR_IDENTITY", "P3-MA-case-file screening (python)")
        if not edgar.get_identity():
            edgar.set_identity(identity)

        company = edgar.Company(ticker.strip().upper())
        rev = _extract_value(company.get_ttm_revenue())
        ni = _extract_value(company.get_ttm_net_income())
        out["revenue"] = rev
        out["net_income"] = ni
        out["source"] = "edgar"
        cache.write_text(json.dumps(out, indent=2))
        return out
    except Exception as exc:
        out["source"] = f"error: {type(exc).__name__}: {exc}"
        # still write whatever we have so the cache path is populated
        try:
            cache.write_text(json.dumps(out, indent=2))
        except Exception:
            pass
        return out


def sanity_check_ticker(ticker: str, use_cache: bool = True) -> Dict[str, object]:
    """Small convenience wrapper the notebook can call directly.

    Returns a human-readable dict with the value, a source note, and a flag
    for whether the pull succeeded.
    """
    facts = fetch_company_facts(ticker, use_cache=use_cache)
    source = facts.get("source") or "unknown"
    ok = source == "edgar"
    return {
        "ticker": facts.get("ticker", ticker.upper()),
        "revenue": facts.get("revenue"),
        "net_income": facts.get("net_income"),
        "source": source,
        "ok": ok,
    }


if __name__ == "__main__":
    # A quick smoke test that does NOT require network when the cache is warm.
    print(sanity_check_ticker("AMZN", use_cache=True))
