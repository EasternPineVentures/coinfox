"""On-chain BTC metrics.

Sources:
- mempool.space: fee recommendations, mempool size, block tip, halving countdown.
- blockchain.info: hashrate, difficulty, unconfirmed tx count, market price.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._http import get_json, get_text

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "source", "added": "2026-05",
     "contribution": "on-chain: mempool.space fees + blockchain.info hashrate + halving countdown"},
]


@dataclass
class OnchainSnapshot:
    fee_fast_sat_vb: Optional[float] = None       # next-block target
    fee_30min_sat_vb: Optional[float] = None
    fee_hour_sat_vb: Optional[float] = None
    mempool_count: Optional[int] = None
    mempool_vsize_vb: Optional[int] = None
    mempool_total_fee_btc: Optional[float] = None
    tip_height: Optional[int] = None
    hashrate_ehs: Optional[float] = None          # exahashes/s
    difficulty: Optional[float] = None
    blocks_to_halving: Optional[int] = None       # rough


def _mempool_fees() -> dict:
    return get_json("https://mempool.space/api/v1/fees/recommended") or {}


def _mempool_stats() -> dict:
    return get_json("https://mempool.space/api/mempool") or {}


def _mempool_tip() -> Optional[int]:
    t = get_text("https://mempool.space/api/blocks/tip/height")
    try:
        return int(t.strip()) if t else None
    except ValueError:
        return None


def _hashrate_ehs() -> Optional[float]:
    # blockchain.info returns hashrate in GH/s
    t = get_text("https://blockchain.info/q/hashrate")
    try:
        gh = float(t.strip()) if t else None
        return gh / 1e9 if gh else None  # GH/s -> EH/s
    except ValueError:
        return None


def _difficulty() -> Optional[float]:
    t = get_text("https://blockchain.info/q/getdifficulty")
    try:
        return float(t.strip()) if t else None
    except ValueError:
        return None


_HALVING_BLOCKS = [210000, 420000, 630000, 840000, 1050000, 1260000, 1470000, 1680000]


def _blocks_to_next_halving(tip: Optional[int]) -> Optional[int]:
    if tip is None:
        return None
    for h in _HALVING_BLOCKS:
        if h > tip:
            return h - tip
    return None


def fetch_onchain() -> OnchainSnapshot:
    snap = OnchainSnapshot()
    fees = _mempool_fees()
    if fees:
        snap.fee_fast_sat_vb = fees.get("fastestFee")
        snap.fee_30min_sat_vb = fees.get("halfHourFee")
        snap.fee_hour_sat_vb = fees.get("hourFee")
    stats = _mempool_stats()
    if stats:
        snap.mempool_count = stats.get("count")
        snap.mempool_vsize_vb = stats.get("vsize")
        try:
            snap.mempool_total_fee_btc = float(stats.get("total_fee", 0)) / 1e8 if stats.get("total_fee") else None
        except (TypeError, ValueError):
            snap.mempool_total_fee_btc = None
    snap.tip_height = _mempool_tip()
    snap.hashrate_ehs = _hashrate_ehs()
    snap.difficulty = _difficulty()
    snap.blocks_to_halving = _blocks_to_next_halving(snap.tip_height)
    return snap
