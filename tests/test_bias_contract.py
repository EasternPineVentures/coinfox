"""Public bias JSON contract regression tests."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import datetime


FORBIDDEN_TEXT = ("stop loss", "SL", "must exit", "guaranteed")


class TestBiasJsonContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "coinfox", "bias", "--symbol", "BTCUSDT", "--json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )
        cls.raw = result.stdout
        cls.payload = json.loads(result.stdout)

    def test_required_top_level_fields(self):
        payload = self.payload
        self.assertIsInstance(payload.get("symbol"), str)
        self.assertIn(payload.get("bias"), {"LONG", "SHORT", "NEUTRAL"})
        self.assertIsInstance(payload.get("thesis"), str)
        self.assertGreater(len(payload["thesis"].strip()), 0)
        self.assertIn("timestamp", payload)
        datetime.fromisoformat(str(payload["timestamp"]).replace("Z", "+00:00"))
        self.assertIn("source_health", payload)
        self.assertTrue(isinstance(payload["source_health"], (dict, str)))
        self.assertIsInstance(payload.get("drivers"), list)

    def test_drivers_include_plain_english_contract(self):
        for driver in self.payload["drivers"]:
            self.assertIsInstance(driver, dict)
            self.assertIsInstance(driver.get("impact"), str)
            self.assertGreater(len(driver["impact"].strip()), 0)
            self.assertIsInstance(driver.get("plain_english"), str)
            self.assertGreater(len(driver["plain_english"].strip()), 0)

    def test_invalidation_contract(self):
        invalidation = self.payload.get("invalidation")
        if self.payload["bias"] == "NEUTRAL":
            self.assertIsNone(invalidation)
            return

        self.assertIsInstance(invalidation, dict)
        self.assertIsInstance(invalidation.get("label"), str)
        self.assertGreater(len(invalidation["label"].strip()), 0)
        self.assertIs(invalidation.get("not_a_stop_loss"), True)

    def test_no_forbidden_user_facing_text(self):
        for value in _walk_strings(self.payload):
            for forbidden in FORBIDDEN_TEXT:
                self.assertNotIn(forbidden, value)


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


if __name__ == "__main__":
    unittest.main()
