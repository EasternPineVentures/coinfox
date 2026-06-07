"""Tests for the Chainlink on-chain price source.

These are offline: the ABI decode helpers are pure, and the network path is
exercised by monkeypatching the module's ``post_json`` so no RPC is hit.
"""

from __future__ import annotations

from coinfox.sources import chainlink


def _abi_encode_round(round_id: int, answer: int, updated_at: int) -> str:
    """Build a latestRoundData() return blob: 5 uint256 words, hex-encoded."""
    words = [round_id, answer & ((1 << 256) - 1), 0, updated_at, round_id]
    return "0x" + "".join(f"{w:064x}" for w in words)


def _abi_encode_uint(value: int) -> str:
    return "0x" + f"{value:064x}"


def test_word_and_int256_decoding():
    blob = _abi_encode_round(round_id=42, answer=64000_00000000, updated_at=1717000000)
    assert chainlink._word(blob, 0) == 42
    assert chainlink._word(blob, 3) == 1717000000
    # negative int256 round-trips
    neg = chainlink._as_int256(chainlink._word(_abi_encode_uint((1 << 256) - 5), 0))
    assert neg == -5


def test_fetch_feed_decodes_price(monkeypatch):
    # 8-decimal feed reporting $64,000.00
    round_blob = _abi_encode_round(round_id=7, answer=6400000000000, updated_at=1717000000)

    def fake_post(url, payload, *a, **k):
        data = payload["params"][0]["data"]
        if data == chainlink._SEL_LATEST_ROUND_DATA:
            return {"result": round_blob}
        if data == chainlink._SEL_DECIMALS:
            return {"result": _abi_encode_uint(8)}
        return None

    monkeypatch.setattr(chainlink, "post_json", fake_post)
    q = chainlink.fetch_feed("BTC/USD", chainlink.FEEDS["BTC/USD"])
    assert q is not None
    assert q.price == 64000.0
    assert q.round_id == 7
    assert q.updated_at == 1717000000


def test_fetch_feed_returns_none_on_rpc_failure(monkeypatch):
    monkeypatch.setattr(chainlink, "post_json", lambda *a, **k: None)
    assert chainlink.fetch_feed("BTC/USD", chainlink.FEEDS["BTC/USD"]) is None


def test_fetch_feed_rejects_nonpositive_answer(monkeypatch):
    bad = _abi_encode_round(round_id=1, answer=0, updated_at=1717000000)
    monkeypatch.setattr(chainlink, "post_json", lambda *a, **k: {"result": bad})
    assert chainlink.fetch_feed("BTC/USD", chainlink.FEEDS["BTC/USD"]) is None


def test_fetch_chainlink_returns_none_when_all_feeds_fail(monkeypatch):
    monkeypatch.setattr(chainlink, "post_json", lambda *a, **k: None)
    assert chainlink.fetch_chainlink() is None


def test_fetch_chainlink_aggregates_available_feeds(monkeypatch):
    round_blob = _abi_encode_round(round_id=1, answer=300000000000, updated_at=1717000000)

    def fake_post(url, payload, *a, **k):
        to = payload["params"][0]["to"]
        data = payload["params"][0]["data"]
        if to != chainlink.FEEDS["ETH/USD"]:
            return None  # only ETH/USD answers
        if data == chainlink._SEL_LATEST_ROUND_DATA:
            return {"result": round_blob}
        if data == chainlink._SEL_DECIMALS:
            return {"result": _abi_encode_uint(8)}
        return None

    monkeypatch.setattr(chainlink, "post_json", fake_post)
    snap = chainlink.fetch_chainlink()
    assert snap is not None
    assert "ETH/USD" in snap.quotes
    assert "BTC/USD" not in snap.quotes
    assert snap.quotes["ETH/USD"].price == 3000.0
