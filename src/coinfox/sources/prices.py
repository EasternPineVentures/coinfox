"""Multi-exchange spot prices for BTC/USD(T).

Sources: Binance, Coinbase, Kraken, Bitstamp, CoinGecko.
Each is independent — any subset failing is fine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Dict, List, Optional

from ._http import get_json

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "source", "added": "2026-05",
     "contribution": "spot prices across Binance/Coinbase/Kraken/Bitstamp/CoinGecko + global market"},
]


@dataclass
class ExchangePrice:
    exchange: str
    pair: str
    price: float


@dataclass
class PriceSnapshot:
    quotes: List[ExchangePrice] = field(default_factory=list)
    median_usd: Optional[float] = None
    spread_pct: Optional[float] = None  # (max-min)/median * 100

    def as_dict(self) -> Dict[str, float]:
        return {q.exchange: q.price for q in self.quotes}


def _binance() -> Optional[ExchangePrice]:
    d = get_json("https://api.binance.com/api/v3/ticker/price", {"symbol": "BTCUSDT"})
    if not d:
        return None
    try:
        return ExchangePrice("binance", "BTCUSDT", float(d["price"]))
    except (KeyError, ValueError):
        return None


def _coinbase() -> Optional[ExchangePrice]:
    d = get_json("https://api.coinbase.com/v2/prices/BTC-USD/spot")
    if not d:
        return None
    try:
        return ExchangePrice("coinbase", "BTC-USD", float(d["data"]["amount"]))
    except (KeyError, ValueError, TypeError):
        return None


def _kraken() -> Optional[ExchangePrice]:
    d = get_json("https://api.kraken.com/0/public/Ticker", {"pair": "XBTUSD"})
    if not d:
        return None
    try:
        result = d["result"]
        first = next(iter(result.values()))
        return ExchangePrice("kraken", "XBTUSD", float(first["c"][0]))
    except (KeyError, ValueError, StopIteration, TypeError):
        return None


def _bitstamp() -> Optional[ExchangePrice]:
    d = get_json("https://www.bitstamp.net/api/v2/ticker/btcusd/")
    if not d:
        return None
    try:
        return ExchangePrice("bitstamp", "btcusd", float(d["last"]))
    except (KeyError, ValueError):
        return None


def _coingecko() -> Optional[ExchangePrice]:
    d = get_json("https://api.coingecko.com/api/v3/simple/price",
                 {"ids": "bitcoin", "vs_currencies": "usd"})
    if not d:
        return None
    try:
        return ExchangePrice("coingecko", "bitcoin/usd", float(d["bitcoin"]["usd"]))
    except (KeyError, ValueError, TypeError):
        return None


_FETCHERS = [_binance, _coinbase, _kraken, _bitstamp, _coingecko]


def fetch_prices() -> PriceSnapshot:
    quotes: List[ExchangePrice] = []
    for fn in _FETCHERS:
        q = fn()
        if q is not None:
            quotes.append(q)
    snap = PriceSnapshot(quotes=quotes)
    if quotes:
        prices = [q.price for q in quotes]
        snap.median_usd = float(median(prices))
        if snap.median_usd:
            snap.spread_pct = (max(prices) - min(prices)) / snap.median_usd * 100.0
    return snap


def fetch_global_market() -> Optional[dict]:
    """CoinGecko global stats: total mcap, BTC dominance, 24h volume."""
    d = get_json("https://api.coingecko.com/api/v3/global")
    if not d:
        return None
    try:
        g = d["data"]
        return {
            "total_market_cap_usd": float(g["total_market_cap"]["usd"]),
            "total_volume_usd": float(g["total_volume"]["usd"]),
            "btc_dominance_pct": float(g["market_cap_percentage"]["btc"]),
            "eth_dominance_pct": float(g["market_cap_percentage"].get("eth", 0.0)),
            "active_cryptocurrencies": int(g.get("active_cryptocurrencies", 0)),
        }
    except (KeyError, ValueError, TypeError):
        return None
