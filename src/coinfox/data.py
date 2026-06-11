"""Core market data fetchers (used by the model).

Klines/price/24h-stats with **multi-exchange fallback**: tries Binance first,
falls back to Kraken, then Coinbase. This keeps coinfox working anywhere on
the planet — Binance is geo-blocked in some regions (HTTP 451).

Broader web sources live in `coinfox.sources`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import requests

BINANCE_BASE = "https://api.binance.com"
COINBASE_BASE = "https://api.exchange.coinbase.com"
KRAKEN_BASE = "https://api.kraken.com"
FNG_URL = "https://api.alternative.me/fng/"

_TIMEFRAMES = {"1m", "5m", "15m", "1h", "4h", "1d"}
USER_AGENT = "coinfox/0.2 (+https://github.com/)"


@dataclass
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int


@dataclass
class FearGreed:
    value: int
    classification: str
    timestamp: int


class DataError(RuntimeError):
    pass


def _get(url: str, params: Optional[dict] = None, timeout: int = 10):
    r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r


# ---------- klines ---------------------------------------------------------

_KRAKEN_INTERVAL = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
_COINBASE_GRANULARITY = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}  # no 4h


def _klines_binance(symbol: str, interval: str, limit: int) -> List[Candle]:
    rows = _get(f"{BINANCE_BASE}/api/v3/klines",
                {"symbol": symbol, "interval": interval, "limit": limit}).json()
    return [
        Candle(int(r[0]), float(r[1]), float(r[2]), float(r[3]),
               float(r[4]), float(r[5]), int(r[6]))
        for r in rows
    ]


def _klines_kraken(symbol: str, interval: str, limit: int) -> List[Candle]:
    if interval not in _KRAKEN_INTERVAL:
        raise DataError(f"Kraken doesn't support timeframe {interval}")
    pair = "XBTUSD" if symbol.upper() in ("BTCUSDT", "BTCUSD", "XBTUSD") else symbol
    d = _get(f"{KRAKEN_BASE}/0/public/OHLC",
             {"pair": pair, "interval": _KRAKEN_INTERVAL[interval]}).json()
    if d.get("error"):
        raise DataError(f"Kraken error: {d['error']}")
    result = d.get("result", {})
    series_key = next((k for k in result if k != "last"), None)
    if not series_key:
        raise DataError("Kraken: no OHLC series in response")
    rows = result[series_key][-limit:]
    out = []
    interval_sec = _KRAKEN_INTERVAL[interval] * 60
    for r in rows:
        t = int(r[0])
        out.append(Candle(t * 1000, float(r[1]), float(r[2]), float(r[3]),
                          float(r[4]), float(r[6]), (t + interval_sec) * 1000))
    return out


def _klines_coinbase(symbol: str, interval: str, limit: int) -> List[Candle]:
    if interval not in _COINBASE_GRANULARITY:
        raise DataError(f"Coinbase doesn't support timeframe {interval}")
    product = "BTC-USD" if symbol.upper() in ("BTCUSDT", "BTCUSD") else symbol
    rows = _get(f"{COINBASE_BASE}/products/{product}/candles",
                {"granularity": _COINBASE_GRANULARITY[interval]}).json()
    # Coinbase returns newest-first: [time, low, high, open, close, volume]
    rows = list(reversed(rows))[-limit:]
    g = _COINBASE_GRANULARITY[interval]
    out = []
    for r in rows:
        t = int(r[0])
        out.append(Candle(t * 1000, float(r[3]), float(r[2]), float(r[1]),
                          float(r[4]), float(r[5]), (t + g) * 1000))
    return out


_KLINE_PROVIDERS: List[Tuple[str, Callable]] = [
    ("binance", _klines_binance),
    ("kraken", _klines_kraken),
    ("coinbase", _klines_coinbase),
]


def fetch_klines(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 250,
                 _used: Optional[List[str]] = None) -> List[Candle]:
    if interval not in _TIMEFRAMES:
        raise DataError(f"Unsupported interval {interval!r}; use one of {sorted(_TIMEFRAMES)}")
    errors = []
    for name, fn in _KLINE_PROVIDERS:
        try:
            out = fn(symbol, interval, limit)
            if out:
                if _used is not None:
                    _used.append(name)
                return out
        except (requests.RequestException, DataError, KeyError, ValueError, TypeError) as e:
            errors.append(f"{name}: {e}")
            continue
    raise DataError("All kline providers failed → " + " | ".join(errors))


# ---------- price ----------------------------------------------------------

def _price_binance(symbol: str) -> float:
    return float(_get(f"{BINANCE_BASE}/api/v3/ticker/price", {"symbol": symbol}).json()["price"])


def _price_coinbase(_symbol: str) -> float:
    return float(_get(f"{COINBASE_BASE}/products/BTC-USD/ticker").json()["price"])


def _price_kraken(_symbol: str) -> float:
    d = _get(f"{KRAKEN_BASE}/0/public/Ticker", {"pair": "XBTUSD"}).json()
    result = d["result"]
    first = next(iter(result.values()))
    return float(first["c"][0])


def fetch_price(symbol: str = "BTCUSDT") -> float:
    for fn in (_price_binance, _price_kraken, _price_coinbase):
        try:
            return fn(symbol)
        except (requests.RequestException, KeyError, ValueError, TypeError, StopIteration):
            continue
    raise DataError("All price providers failed")


def _spot_coinbase(symbol: str) -> float:
    """Symbol-aware Coinbase spot (US-accessible, unlike Binance). Maps a pair
    like BTCUSDT/BTCUSD -> BTC-USD."""
    base = symbol.upper()
    for suffix in ("USDT", "USDC", "USD"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    quote = "https://api.coinbase.com/v2/prices/" + f"{base}-USD/spot"
    data = _get(quote).json()
    return float(data["data"]["amount"])


def fetch_spot(symbol: str) -> float:
    """Symbol-SAFE live price. Unlike :func:`fetch_price`, this never falls back
    to a BTC-hardcoded provider, so an unknown symbol (e.g. an equity ticker we
    can't price) raises ``DataError`` instead of silently returning Bitcoin's
    price. Tries Binance then Coinbase so it still works from US IPs (Binance is
    geoblocked there). Equities have no provider here -> ``DataError``."""
    clean = str(symbol or "").strip().upper()
    if not clean:
        raise DataError("symbol is required")
    for fn in (_price_binance, _spot_coinbase):
        try:
            return fn(clean)
        except (requests.RequestException, KeyError, ValueError, TypeError):
            continue
    raise DataError(f"no live price for {clean}")


# ---------- 24h stats -----------------------------------------------------

def fetch_24h_stats(symbol: str = "BTCUSDT") -> dict:
    # try Binance first
    try:
        return _get(f"{BINANCE_BASE}/api/v3/ticker/24hr", {"symbol": symbol}).json()
    except requests.RequestException:
        pass
    # Kraken fallback
    try:
        d = _get(f"{KRAKEN_BASE}/0/public/Ticker", {"pair": "XBTUSD"}).json()
        first = next(iter(d["result"].values()))
        last = float(first["c"][0])
        open_ = float(first["o"])
        change_pct = (last - open_) / open_ * 100.0 if open_ else 0.0
        return {
            "lastPrice": str(last),
            "openPrice": str(open_),
            "priceChangePercent": f"{change_pct:.4f}",
            "highPrice": first["h"][1],
            "lowPrice": first["l"][1],
            "volume": first["v"][1],
        }
    except (requests.RequestException, KeyError, ValueError, StopIteration):
        pass
    raise DataError("All 24h stats providers failed")


# ---------- Fear & Greed ---------------------------------------------------

def fetch_fear_greed() -> Optional[FearGreed]:
    try:
        data = _get(FNG_URL, {"limit": 1}).json()["data"][0]
        return FearGreed(int(data["value"]), data["value_classification"], int(data["timestamp"]))
    except (requests.RequestException, KeyError, ValueError, IndexError):
        return None
