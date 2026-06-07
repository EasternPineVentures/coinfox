"""Chainlink Data Feeds — decentralized on-chain price as a cross-check.

CoinFox already medians several CeFi REST prices (see :mod:`coinfox.sources.prices`).
This source adds an *independent, decentralized* reference: it reads a Chainlink
price feed directly from an Ethereum node via a raw ``eth_call`` to the feed
aggregator's ``latestRoundData()``. Comparing the two surfaces is a cheap way to
catch a bad or manipulated CeFi quote.

Design notes
------------
- **Keyless by default.** It hits a public RPC endpoint and needs no API key.
  Public RPCs are rate-limited and occasionally flaky, so like every CoinFox
  source this is *best-effort*: it returns ``None`` on any failure and never
  raises into the aggregator. Point it at your own node/provider by setting
  ``COINFOX_ETH_RPC_URL`` (e.g. an Alchemy/Infura URL) for reliability.
- **No dependencies.** We encode the call and decode the response by hand rather
  than pulling in ``web3``, keeping CoinFox lean and install-light.
- **Read-only.** This never sends a transaction, spends gas, or touches LINK —
  it only reads public on-chain data, consistent with CoinFox having no coin,
  no token, and no on-chain settlement.

Docs: https://docs.chain.link/data-feeds
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

from ._http import post_json

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "source", "added": "2026-06",
     "contribution": "Chainlink on-chain Data Feed price cross-check (keyless, read-only)"},
]

# Public, keyless Ethereum JSON-RPC endpoint. Override with COINFOX_ETH_RPC_URL.
DEFAULT_RPC_URL = "https://ethereum-rpc.publicnode.com"

# Chainlink mainnet Data Feed aggregator-proxy addresses.
# https://docs.chain.link/data-feeds/price-feeds/addresses
FEEDS: Dict[str, str] = {
    "BTC/USD": "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",
    "ETH/USD": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
}

# Function selectors (first 4 bytes of keccak256 of the signature).
_SEL_LATEST_ROUND_DATA = "0xfeaf968c"  # latestRoundData()
_SEL_DECIMALS = "0x313ce567"           # decimals()


@dataclass
class ChainlinkQuote:
    pair: str
    price: float
    feed_address: str
    updated_at: int          # unix seconds of the on-chain round
    round_id: int


@dataclass
class ChainlinkSnapshot:
    quotes: Dict[str, ChainlinkQuote]

    def as_dict(self) -> Dict[str, float]:
        return {pair: q.price for pair, q in self.quotes.items()}


def _rpc_url() -> str:
    return os.environ.get("COINFOX_ETH_RPC_URL", "").strip() or DEFAULT_RPC_URL


def _eth_call(to: str, selector: str) -> Optional[str]:
    """Return the hex result string of an ``eth_call``, or None on failure."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": to, "data": selector}, "latest"],
    }
    d = post_json(_rpc_url(), payload)
    if not isinstance(d, dict):
        return None
    result = d.get("result")
    if not isinstance(result, str) or not result.startswith("0x") or len(result) <= 2:
        return None
    return result


def _word(hex_result: str, index: int) -> int:
    """Decode the Nth 32-byte word of an ABI-encoded hex result as a uint."""
    body = hex_result[2:]
    start = index * 64
    return int(body[start:start + 64], 16)


def _as_int256(value: int) -> int:
    """Reinterpret a 256-bit word as a signed integer (feeds return int256)."""
    if value >= 1 << 255:
        return value - (1 << 256)
    return value


def fetch_feed(pair: str, address: str) -> Optional[ChainlinkQuote]:
    """Read one Chainlink price feed. Best-effort: returns None on any failure."""
    raw = _eth_call(address, _SEL_LATEST_ROUND_DATA)
    if raw is None:
        return None
    try:
        # latestRoundData() -> (roundId, answer, startedAt, updatedAt, answeredInRound)
        round_id = _word(raw, 0)
        answer = _as_int256(_word(raw, 1))
        updated_at = _word(raw, 3)
        if answer <= 0:
            return None
        dec_raw = _eth_call(address, _SEL_DECIMALS)
        decimals = _word(dec_raw, 0) if dec_raw else 8  # USD feeds are 8 dp
        price = answer / (10 ** decimals)
    except (ValueError, IndexError, ZeroDivisionError):
        return None
    return ChainlinkQuote(
        pair=pair,
        price=float(price),
        feed_address=address,
        updated_at=int(updated_at),
        round_id=int(round_id),
    )


def fetch_chainlink() -> Optional[ChainlinkSnapshot]:
    """Read all configured Chainlink feeds. Returns None if none could be read."""
    quotes: Dict[str, ChainlinkQuote] = {}
    for pair, address in FEEDS.items():
        q = fetch_feed(pair, address)
        if q is not None:
            quotes[pair] = q
    if not quotes:
        return None
    return ChainlinkSnapshot(quotes=quotes)
