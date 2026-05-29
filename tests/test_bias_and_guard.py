"""Tests for product-level bias reads and community guardrails."""

import tempfile
import unittest
from pathlib import Path

from coinfox.bias import bias_label, compute_invalidation, from_verdict
from coinfox.community.guard import assess_request
from coinfox.community.trust import ReputationLedger, tier_for_score
from coinfox.model import Signal, Verdict


class TestBiasRead(unittest.TestCase):
    def test_bias_label_thresholds(self):
        self.assertEqual(bias_label(0.60), "LONG")
        self.assertEqual(bias_label(0.40), "SHORT")
        self.assertEqual(bias_label(0.50), "NEUTRAL")

    def test_from_verdict_returns_public_contract(self):
        verdict = Verdict(
            probability_up=0.61,
            confidence=0.72,
            bias="long",
            horizon_candles=4,
            signals=[
                Signal("trend_ema", 1.0, 1.4, "EMA stack up"),
                Signal("rsi", -0.2, 1.0, "RSI warm"),
            ],
        )
        read = from_verdict("spy", "1h", 4, verdict, price=500.0, change_24h_pct=1.2)
        self.assertEqual(read.symbol, "SPY")
        self.assertEqual(read.bias, "LONG")
        self.assertEqual(read.conviction, 0.72)
        self.assertEqual(read.probability_down, 0.39)
        self.assertEqual(read.regime_hint, "high-conviction")
        self.assertEqual(read.drivers[0]["lean"], "LONG")
        self.assertEqual(read.drivers[0]["impact"], "bullish")
        self.assertIn("plain_english", read.drivers[0])
        self.assertEqual(read.invalidation.type, "price_below")
        self.assertEqual(read.invalidation.label, "Thesis weakens below")
        self.assertEqual(read.source_health.status, "healthy")
        self.assertIn("LONG on SPY", read.human_readable)

    def test_short_bias_json_includes_invalidation_contract(self):
        verdict = Verdict(
            probability_up=0.39,
            confidence=0.75,
            bias="short",
            horizon_candles=4,
            signals=[
                Signal("resistance_rejection", -1.0, 1.2, "price rejected resistance at $185"),
            ],
            extras={"last_close": 185.0, "ema200": 184.25},
        )
        read = from_verdict("sol", "1h", 4, verdict, price=185.0)
        payload = read.as_dict()

        self.assertEqual(payload["bias"], "SHORT")
        self.assertEqual(payload["conviction"], 0.75)
        self.assertEqual(payload["thesis"], payload["human_readable"])
        self.assertEqual(payload["timestamp"], payload["updated_at"])
        self.assertEqual(payload["source_health"]["status"], "healthy")
        self.assertEqual(payload["invalidation"]["type"], "price_above")
        self.assertEqual(payload["invalidation"]["label"], "Thesis weakens above")
        self.assertTrue(payload["invalidation"]["not_a_stop_loss"])
        self.assertGreater(payload["invalidation"]["level"], 185.0)
        self.assertIn("The short thesis weakens if price closes above", payload["human_readable"])

    def test_compute_invalidation_uses_swing_level_and_buffer(self):
        short_rule = compute_invalidation("SHORT", 100.0, 105.0, 95.0)
        long_rule = compute_invalidation("LONG", 100.0, 105.0, 95.0)

        self.assertIsNotNone(short_rule)
        self.assertEqual(short_rule.type, "price_above")
        self.assertEqual(short_rule.level, 105.5)
        self.assertEqual(short_rule.label, "Thesis weakens above")

        self.assertIsNotNone(long_rule)
        self.assertEqual(long_rule.type, "price_below")
        self.assertEqual(long_rule.level, 94.5)
        self.assertEqual(long_rule.label, "Thesis weakens below")


class TestCommunityGuard(unittest.TestCase):
    def test_guard_blocks_secret_leaks(self):
        report = assess_request(
            "help with key",
            "api_key = sk-abcdefghijklmnopqrstuvwxyz123456",
        )
        self.assertEqual(report.risk, "high")
        self.assertTrue(report.should_block)

    def test_guard_flags_sensitive_files_without_blocking(self):
        report = assess_request(
            "Tune model weights",
            "Small transparent model tuning proposal.",
            author_association="FIRST_TIME_CONTRIBUTOR",
            changed_files=["src/coinfox/model.py"],
        )
        self.assertEqual(report.risk, "medium")
        self.assertFalse(report.should_block)

    def test_reputation_ledger_scores_contributors(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ReputationLedger(Path(tmp) / "trust.jsonl")
            ledger.record("Builder", "pr_merged", ref="#12")
            ledger.record("builder", "docs_merged", ref="#14")
            rep = ledger.reputation("@builder")
        self.assertEqual(rep.score, 16)
        self.assertEqual(rep.tier, "known")
        self.assertEqual(tier_for_score(50), "maintainer-track")


if __name__ == "__main__":
    unittest.main()
