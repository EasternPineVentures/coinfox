"""Sentiment sources.

- alternative.me Fear & Greed (and 30-day history for trend)
- CoinGecko sentiment_votes_up_percentage for bitcoin
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ._http import get_json

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "source", "added": "2026-05",
     "contribution": "Fear & Greed (30d history) + CoinGecko community/dev scores"},
]


@dataclass
class FNGPoint:
    value: int
    classification: str
    timestamp: int


@dataclass
class SentimentSnapshot:
    fng_now: Optional[FNGPoint] = None
    fng_yesterday: Optional[FNGPoint] = None
    fng_week_ago: Optional[FNGPoint] = None
    fng_history_30d: List[FNGPoint] = field(default_factory=list)
    coingecko_up_votes_pct: Optional[float] = None
    coingecko_community_score: Optional[float] = None
    coingecko_developer_score: Optional[float] = None


def _fng_history(limit: int = 30) -> List[FNGPoint]:
    d = get_json("https://api.alternative.me/fng/", {"limit": limit})
    out: List[FNGPoint] = []
    if not d:
        return out
    for row in d.get("data", []):
        try:
            out.append(FNGPoint(int(row["value"]), row["value_classification"], int(row["timestamp"])))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def fetch_sentiment() -> SentimentSnapshot:
    snap = SentimentSnapshot()
    history = _fng_history(30)
    snap.fng_history_30d = history
    if history:
        snap.fng_now = history[0]
        if len(history) > 1:
            snap.fng_yesterday = history[1]
        if len(history) > 7:
            snap.fng_week_ago = history[7]

    cg = get_json("https://api.coingecko.com/api/v3/coins/bitcoin",
                  params={
                      "localization": "false", "tickers": "false",
                      "market_data": "false", "community_data": "true",
                      "developer_data": "true", "sparkline": "false",
                  })
    if cg:
        try:
            snap.coingecko_up_votes_pct = float(cg.get("sentiment_votes_up_percentage")) \
                if cg.get("sentiment_votes_up_percentage") is not None else None
            snap.coingecko_community_score = cg.get("community_score")
            snap.coingecko_developer_score = cg.get("developer_score")
        except (KeyError, ValueError, TypeError):
            pass
    return snap
