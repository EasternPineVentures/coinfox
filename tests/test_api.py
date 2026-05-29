"""HTTP API contract tests for the public CoinFox surface."""

from __future__ import annotations

import json
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import coinfox.api as api_module
from coinfox.api import app


class _FakeBiasRead:
    def __init__(self, payload: dict):
        self._payload = payload

    def as_dict(self) -> dict:
        return dict(self._payload)


class TestCoinFoxApi(unittest.TestCase):
    def setUp(self) -> None:
        api_module._BIAS_CACHE.clear()
        self.client = TestClient(app)

    def test_bias_returns_contract_payload(self):
        payload = _bias_payload()
        with patch("coinfox.api.get_bias", return_value=_FakeBiasRead(payload)):
            response = self.client.get("/bias?symbol=BTCUSDT")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["symbol"], "BTCUSDT")
        self.assertIn(data["bias"], {"LONG", "SHORT", "NEUTRAL"})
        self.assertIsInstance(data["thesis"], str)
        self.assertGreater(len(data["thesis"]), 0)
        self.assertIn("timestamp", data)
        self.assertIn("source_health", data)
        self.assertIsInstance(data["drivers"], list)
        for driver in data["drivers"]:
            self.assertIsInstance(driver["impact"], str)
            self.assertIsInstance(driver["plain_english"], str)
        self.assertIs(data["invalidation"]["not_a_stop_loss"], True)

    def test_bias_rejects_invalid_symbol(self):
        response = self.client.get("/bias?symbol=INVALID")
        self.assertEqual(response.status_code, 400)

    def test_health_returns_ok(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertIn("timestamp", response.json())

    def test_terms_matches_packaged_terms_file(self):
        response = self.client.get("/terms")
        self.assertEqual(response.status_code, 200)
        path = Path(__file__).resolve().parents[1] / "src" / "coinfox" / "assets" / "terms.json"
        expected = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(response.json(), expected)

    def test_feedback_accepts_valid_payload(self):
        payload = {
            "anonymous_user_id": str(uuid.uuid4()),
            "symbol": "BTCUSDT",
            "bias_shown": "LONG",
            "confidence_shown": 0.72,
            "user_action": "thumbs_up",
            "comment": "Clear read.",
        }
        with patch("coinfox.api.record_feedback", return_value=456):
            response = self.client.post("/feedback", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], 456)

    def test_feedback_rejects_missing_required_fields(self):
        response = self.client.post("/feedback", json={"symbol": "BTCUSDT"})
        self.assertEqual(response.status_code, 422)


def _bias_payload() -> dict:
    return {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "horizon": 4,
        "bias": "LONG",
        "conviction": 0.72,
        "thesis": "BTC is leaning long because price is holding above recent support.",
        "invalidation": {
            "type": "price_below",
            "label": "Thesis weakens below",
            "level": 67250.0,
            "reason": "A move below this zone would break the recent support structure.",
            "not_a_stop_loss": True,
        },
        "human_readable": "BTC is leaning long because price is holding above recent support.",
        "probability_up": 0.64,
        "probability_down": 0.36,
        "confidence": 0.72,
        "price": 68100.0,
        "change_24h_pct": 1.2,
        "regime_hint": "directional",
        "updated_at": "2026-05-29T00:00:00+00:00",
        "timestamp": "2026-05-29T00:00:00+00:00",
        "drivers": [
            {
                "name": "Trend",
                "impact": "bullish",
                "plain_english": "Price is holding above the short-term moving average.",
            }
        ],
        "source_health": {"status": "healthy", "stale_sources": [], "notes": []},
    }


if __name__ == "__main__":
    unittest.main()
