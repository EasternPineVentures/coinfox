"""Macro context: DXY proxy (UUP ETF), gold (GLD ETF), via Stooq (no key).

Stooq offers free EOD CSV without auth — good enough for daily macro context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from ._http import get_text

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "source", "added": "2026-05",
     "contribution": "macro context: DXY, gold, silver, WTI, Brent, SPX, US10Y via Stooq"},
]


@dataclass
class MacroSnapshot:
    series: Dict[str, float] = field(default_factory=dict)         # latest close
    changes_pct: Dict[str, float] = field(default_factory=dict)    # vs prior close


STOOQ = {
    # DXY US dollar index
    "DXY": "https://stooq.com/q/d/l/?s=^dxy&i=d",
    # Gold spot (USD/oz)
    "GOLD": "https://stooq.com/q/d/l/?s=xauusd&i=d",
    # Silver spot (USD/oz)
    "SILVER": "https://stooq.com/q/d/l/?s=xagusd&i=d",
    # WTI crude oil (USD/bbl)
    "WTI": "https://stooq.com/q/d/l/?s=cl.f&i=d",
    # Brent crude oil (USD/bbl)
    "BRENT": "https://stooq.com/q/d/l/?s=b.f&i=d",
    # S&P 500
    "SPX": "https://stooq.com/q/d/l/?s=^spx&i=d",
    # US 10Y yield
    "US10Y": "https://stooq.com/q/d/l/?s=10usy.b&i=d",
    # Gold / Silver ratio context: BTC/Gold ratio approximated separately by app
}


def _last_two_closes(csv: str) -> Optional[tuple[float, float]]:
    lines = [ln for ln in csv.strip().splitlines() if ln and not ln.startswith("Date")]
    if len(lines) < 2:
        return None
    try:
        last = float(lines[-1].split(",")[4])
        prev = float(lines[-2].split(",")[4])
        return last, prev
    except (ValueError, IndexError):
        return None


def fetch_macro() -> MacroSnapshot:
    snap = MacroSnapshot()
    for name, url in STOOQ.items():
        csv = get_text(url, timeout=8)
        if not csv:
            continue
        pair = _last_two_closes(csv)
        if not pair:
            continue
        last, prev = pair
        snap.series[name] = last
        if prev:
            snap.changes_pct[name] = (last - prev) / prev * 100.0
    return snap
