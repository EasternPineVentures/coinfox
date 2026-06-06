"""NY Fox Exchange paper-trading API tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from coinfox.community.arena import Arena
from coinfox.community.social import SocialStore

try:
    from fastapi.testclient import TestClient

    from coinfox.api import app
except Exception:  # pragma: no cover - optional API extras may be absent
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None or app is None, "FastAPI extras not installed")
class TestExchangeApi(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.price = {"BTCUSDT": 100.0}
        arena = Arena(
            db_path=base / "community.sqlite",
            identity_path=base / "identity",
            price_fetcher=lambda symbol: self.price.get(symbol.upper(), 100.0),
        )
        social = SocialStore(base / "social.sqlite")
        self._patches = [
            patch("coinfox.api._ARENA", arena),
            patch("coinfox.api._SOCIAL", social),
        ]
        for p in self._patches:
            p.start()
        self.client = TestClient(app)

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def _new_user(self, name="trader"):
        return self.client.post("/api/users", json={"username": name}).json()

    def test_session_endpoint_reports_window(self):
        session = self.client.get("/api/exchange/session").json()
        self.assertIn("is_open", session)
        self.assertIn("opens_at_ts", session)
        self.assertFalse(session["enforced"])  # 24/7 by default in tests

    def test_open_then_close_position_settles_gold(self):
        user = self._new_user("alpha")
        headers = {"x-user-id": user["id"]}
        self.assertEqual(user["gold"], 500)  # starting Gold from the arena

        opened = self.client.post(
            "/api/exchange/positions",
            json={"symbol": "BTCUSDT", "direction": "long", "amount": 100},
            headers=headers,
        )
        self.assertEqual(opened.status_code, 200, opened.text)
        position_id = opened.json()["id"]

        # Stake left the balance; the gold next to the name reflects it.
        self.assertEqual(self.client.get(f"/api/users/{user['id']}").json()["gold"], 400)

        # Price moves up 20% -> long position shows unrealized profit.
        self.price["BTCUSDT"] = 120.0
        listing = self.client.get("/api/exchange/positions", headers=headers).json()
        self.assertEqual(len(listing["positions"]), 1)
        self.assertGreater(listing["positions"][0]["unrealized_pnl"], 0)
        self.assertEqual(listing["stats"]["open_positions"], 1)

        closed = self.client.post(
            f"/api/exchange/positions/{position_id}/close",
            headers=headers,
        )
        self.assertEqual(closed.status_code, 200, closed.text)
        self.assertGreater(closed.json()["realized_pnl"], 0)

        # Realized profit returns to Gold -> balance is now above the start.
        self.assertGreater(self.client.get(f"/api/users/{user['id']}").json()["gold"], 500)

    def test_open_requires_user_and_rejects_bad_direction(self):
        anon = self.client.post(
            "/api/exchange/positions",
            json={"symbol": "BTCUSDT", "direction": "long", "amount": 10},
        )
        self.assertEqual(anon.status_code, 401)

        user = self._new_user("beta")
        bad = self.client.post(
            "/api/exchange/positions",
            json={"symbol": "BTCUSDT", "direction": "sideways", "amount": 10},
            headers={"x-user-id": user["id"]},
        )
        self.assertEqual(bad.status_code, 400)

    def test_cannot_overstake_gold(self):
        user = self._new_user("gamma")
        over = self.client.post(
            "/api/exchange/positions",
            json={"symbol": "BTCUSDT", "direction": "long", "amount": 999999},
            headers={"x-user-id": user["id"]},
        )
        self.assertEqual(over.status_code, 400)

    def test_leaderboard_returns_traders(self):
        user = self._new_user("delta")
        self.client.post(
            "/api/exchange/positions",
            json={"symbol": "BTCUSDT", "direction": "long", "amount": 50},
            headers={"x-user-id": user["id"]},
        )
        leaders = self.client.get("/api/exchange/leaderboard").json()["leaders"]
        self.assertTrue(any(stat["handle"] == "delta" for stat in leaders))


if __name__ == "__main__":
    unittest.main()
