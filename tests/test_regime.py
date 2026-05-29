"""Unit tests for regime detection and benchmark behavior."""

import unittest
from datetime import datetime, timedelta

from coinfox.ai.regime import (
    RegimeConfig,
    RegimeDetector,
    run_regime_benchmark,
    score_regime_config,
    synthetic_regime_cases,
    tune_regime_thresholds,
)


class TestRegimeDetector(unittest.TestCase):
    def test_trend_detected_on_persistent_uptrend(self):
        det = RegimeDetector()
        ts = datetime(2026, 1, 1)
        price = 100.0
        for i in range(140):
            price *= 1.0015
            det.update(price, 1000.0 + i, ts + timedelta(minutes=i))

        regime, confidence = det.get_regime()
        self.assertEqual(regime, "trend")
        self.assertGreaterEqual(confidence, 0.6)

    def test_panic_detected_on_fast_drop_with_volume_spike(self):
        det = RegimeDetector()
        ts = datetime(2026, 1, 1)
        price = 100.0
        for i in range(30):
            det.update(price, 1000.0, ts + timedelta(minutes=i))

        # Force a fast drawdown with large volume expansion.
        for j in range(5):
            price *= 0.985
            vol = 4000.0 if j == 4 else 1500.0
            det.update(price, vol, ts + timedelta(minutes=30 + j))

        regime, confidence = det.get_regime()
        self.assertEqual(regime, "panic")
        self.assertGreater(confidence, 0.5)

    def test_macro_shock_hint_overrides_local_regime(self):
        det = RegimeDetector()
        ts = datetime(2026, 1, 1)
        for i in range(30):
            det.update(100.0 + i * 0.05, 1000.0, ts + timedelta(minutes=i))

        regime, confidence = det.get_regime(panic_ratio_hint=0.8)
        self.assertEqual(regime, "macro_shock")
        self.assertGreaterEqual(confidence, 0.9)


class TestRegimeBenchmark(unittest.TestCase):
    def test_benchmark_returns_consistent_metrics(self):
        out = run_regime_benchmark(symbols=25, updates_per_symbol=120, window_size=80, seed=42)
        self.assertEqual(out["symbols"], 25)
        self.assertEqual(out["updates_per_symbol"], 120)
        self.assertEqual(out["total_updates"], 3000)
        self.assertGreater(out["elapsed_s"], 0.0)
        self.assertGreater(out["updates_per_s"], 0.0)
        self.assertGreater(out["us_per_update"], 0.0)
        self.assertIn("trend_strength", out["sample_metrics"])


class TestRegimeTuner(unittest.TestCase):
    def test_score_regime_config_returns_confusion_matrix(self):
        score = score_regime_config(RegimeConfig(), synthetic_regime_cases(seed=21))
        self.assertGreater(score["sample_size"], 0)
        self.assertGreaterEqual(score["accuracy"], 0.50)
        self.assertIn("trend", score["confusion"])
        self.assertIn("panic_price_drop_pct", score["config"])

    def test_tuner_returns_config_not_worse_than_baseline(self):
        result = tune_regime_thresholds(seed=21)
        self.assertGreaterEqual(result["best"]["accuracy"], result["baseline"]["accuracy"])
        self.assertIn("recommended_config", result)
        self.assertIn("trend_strength_threshold", result["recommended_config"])


if __name__ == "__main__":
    unittest.main()
