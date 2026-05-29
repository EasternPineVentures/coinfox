"""Derivatives: funding rates, open interest, basis.

Sources:
- Binance USDT-M futures (BTCUSDT perp): funding + OI + premium index.
- Bybit linear perpetuals (BTCUSDT): funding.
- OKX swap (BTC-USDT-SWAP): funding + OI.
- Deribit (BTC-PERPETUAL): funding + index/mark for basis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Dict, List, Optional

from ._http import get_json

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "source", "added": "2026-05",
     "contribution": "derivatives: funding + open interest + basis from Binance/Bybit/OKX/Deribit"},
]


@dataclass
class Funding:
    venue: str
    symbol: str
    rate: float          # 8h funding rate (e.g. 0.0001 = 0.01%)
    annualized_pct: float


@dataclass
class OpenInterest:
    venue: str
    symbol: str
    contracts: Optional[float] = None
    notional_usd: Optional[float] = None


@dataclass
class DerivSnapshot:
    funding: List[Funding] = field(default_factory=list)
    open_interest: List[OpenInterest] = field(default_factory=list)
    avg_funding: Optional[float] = None              # average across venues
    avg_funding_annualized_pct: Optional[float] = None
    basis_pct: Optional[float] = None                # (mark - index) / index * 100


def _ann(rate: float, per_day: int = 3) -> float:
    return rate * per_day * 365 * 100.0


def _binance_funding() -> Optional[Funding]:
    d = get_json("https://fapi.binance.com/fapi/v1/premiumIndex", {"symbol": "BTCUSDT"})
    if not d:
        return None
    try:
        r = float(d["lastFundingRate"])
        return Funding("binance", "BTCUSDT", r, _ann(r))
    except (KeyError, ValueError, TypeError):
        return None


def _binance_oi() -> Optional[OpenInterest]:
    d = get_json("https://fapi.binance.com/fapi/v1/openInterest", {"symbol": "BTCUSDT"})
    if not d:
        return None
    try:
        contracts = float(d["openInterest"])
        # try notional via 24h ticker for last price
        t = get_json("https://fapi.binance.com/fapi/v1/ticker/price", {"symbol": "BTCUSDT"})
        notional = contracts * float(t["price"]) if t and "price" in t else None
        return OpenInterest("binance", "BTCUSDT", contracts, notional)
    except (KeyError, ValueError, TypeError):
        return None


def _bybit_funding() -> Optional[Funding]:
    d = get_json("https://api.bybit.com/v5/market/tickers",
                 {"category": "linear", "symbol": "BTCUSDT"})
    if not d:
        return None
    try:
        item = d["result"]["list"][0]
        r = float(item["fundingRate"])
        return Funding("bybit", "BTCUSDT", r, _ann(r))
    except (KeyError, ValueError, IndexError, TypeError):
        return None


def _bybit_oi() -> Optional[OpenInterest]:
    d = get_json("https://api.bybit.com/v5/market/tickers",
                 {"category": "linear", "symbol": "BTCUSDT"})
    if not d:
        return None
    try:
        item = d["result"]["list"][0]
        oi_value = float(item.get("openInterestValue", 0.0)) or None
        oi_contracts = float(item.get("openInterest", 0.0)) or None
        return OpenInterest("bybit", "BTCUSDT", oi_contracts, oi_value)
    except (KeyError, ValueError, IndexError, TypeError):
        return None


def _okx_funding() -> Optional[Funding]:
    d = get_json("https://www.okx.com/api/v5/public/funding-rate",
                 {"instId": "BTC-USDT-SWAP"})
    if not d:
        return None
    try:
        item = d["data"][0]
        r = float(item["fundingRate"])
        return Funding("okx", "BTC-USDT-SWAP", r, _ann(r))
    except (KeyError, ValueError, IndexError, TypeError):
        return None


def _okx_oi() -> Optional[OpenInterest]:
    d = get_json("https://www.okx.com/api/v5/public/open-interest",
                 {"instId": "BTC-USDT-SWAP"})
    if not d:
        return None
    try:
        item = d["data"][0]
        contracts = float(item.get("oi", 0.0)) or None
        notional = float(item.get("oiUsd", 0.0)) or None
        return OpenInterest("okx", "BTC-USDT-SWAP", contracts, notional)
    except (KeyError, ValueError, IndexError, TypeError):
        return None


def _deribit_funding_and_basis() -> tuple[Optional[Funding], Optional[float]]:
    d = get_json("https://www.deribit.com/api/v2/public/ticker",
                 {"instrument_name": "BTC-PERPETUAL"})
    if not d:
        return None, None
    try:
        res = d["result"]
        r = float(res.get("current_funding", 0.0))
        funding = Funding("deribit", "BTC-PERPETUAL", r, _ann(r, per_day=24))  # continuous-ish
        mark = float(res["mark_price"])
        index = float(res["index_price"])
        basis = (mark - index) / index * 100.0 if index else None
        return funding, basis
    except (KeyError, ValueError, TypeError):
        return None, None


def fetch_derivatives() -> DerivSnapshot:
    snap = DerivSnapshot()
    for f in (_binance_funding, _bybit_funding, _okx_funding):
        x = f()
        if x:
            snap.funding.append(x)
    deribit_f, basis = _deribit_funding_and_basis()
    if deribit_f:
        snap.funding.append(deribit_f)
    snap.basis_pct = basis
    for f in (_binance_oi, _bybit_oi, _okx_oi):
        x = f()
        if x:
            snap.open_interest.append(x)
    # average funding across 8h-cycle venues (exclude deribit which is continuous)
    eight_hour = [f.rate for f in snap.funding if f.venue != "deribit"]
    if eight_hour:
        snap.avg_funding = mean(eight_hour)
        snap.avg_funding_annualized_pct = _ann(snap.avg_funding)
    return snap
