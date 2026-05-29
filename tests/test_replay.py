"""Tests for pulse replay quality gates."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from coinfox.ai.churn import SCHEMA
from coinfox.ai.replay import (
    ReplayThought,
    evaluate_replay,
    load_replay_thoughts,
    quality_gate,
    run_replay_quality_gate,
    synthetic_replay_thoughts,
)


class TestReplayQualityGate(unittest.TestCase):
    def test_synthetic_replay_gate_passes(self):
        result = run_replay_quality_gate(
            synthetic=True,
            horizon_steps=3,
            min_sample_size=30,
            min_hit_rate=0.80,
            max_brier_like=0.25,
        )
        self.assertTrue(result["passed"])
        self.assertGreaterEqual(result["report"]["sample_size"], 30)
        self.assertGreaterEqual(result["report"]["hit_rate"], 0.80)

    def test_gate_fails_when_bias_is_consistently_wrong(self):
        thoughts = []
        price = 100.0
        for i in range(40):
            price *= 1.003
            thoughts.append(
                ReplayThought(
                    ts=1000 + i,
                    bias="short",
                    conviction=4,
                    digest={"price_median_usd": price},
                )
            )

        report = evaluate_replay(thoughts, horizon_steps=3)
        result = quality_gate(
            report,
            min_sample_size=30,
            min_hit_rate=0.80,
            max_brier_like=0.25,
        )
        self.assertLess(report["hit_rate"], 0.20)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["hit_rate"])

    def test_load_replay_thoughts_from_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "churn.sqlite"
            with closing(sqlite3.connect(db_path)) as conn, conn:
                conn.executescript(SCHEMA)
                for ts, bias, price in (
                    (3, "short", 98.0),
                    (1, "long", 100.0),
                    (2, "neutral", 100.1),
                ):
                    conn.execute(
                        "INSERT INTO thoughts "
                        "(ts, bias, conviction, headline, body, provider, model, cost_tier, digest) "
                        "VALUES (?, ?, 3, 'h', 'b', 'p', 'm', 'local', ?)",
                        (ts, bias, json.dumps({"price_median_usd": price})),
                    )

            rows = load_replay_thoughts(db_path, limit=10)
        self.assertEqual([row.ts for row in rows], [1, 2, 3])
        self.assertEqual(rows[0].bias, "long")

    def test_synthetic_fixture_has_all_biases(self):
        thoughts = synthetic_replay_thoughts()
        biases = {thought.bias for thought in thoughts}
        self.assertEqual(biases, {"long", "neutral", "short"})


if __name__ == "__main__":
    unittest.main()
