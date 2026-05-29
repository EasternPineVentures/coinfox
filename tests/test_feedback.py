"""Tests for anonymous feedback reporting."""

import tempfile
import unittest
from pathlib import Path

from coinfox.feedback import FeedbackEvent, FeedbackStore, build_feedback_report


class TestFeedbackLearning(unittest.TestCase):
    def test_records_feedback_and_builds_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "feedback.sqlite"
            store = FeedbackStore(db)
            store.record(
                FeedbackEvent(
                    anonymous_user_id="local-random-id",
                    symbol="btcusdt",
                    bias_shown="short",
                    confidence_shown=0.71,
                    user_feedback="disagree",
                    user_invalidation_level=70800,
                    comment="Resistance is higher on my chart.",
                    timestamp="2026-05-29T00:00:00Z",
                )
            )
            store.record(
                FeedbackEvent(
                    anonymous_user_id="local-random-id",
                    symbol="BTCUSDT",
                    bias_shown="SHORT",
                    confidence_shown=0.70,
                    user_feedback="adjusted_invalidation",
                    user_invalidation_level=71000,
                    timestamp="2026-05-29T00:01:00Z",
                )
            )

            report = build_feedback_report(db_path=db, symbol="btcusdt")

        self.assertEqual(report.total_events, 2)
        self.assertEqual(report.symbol, "BTCUSDT")
        self.assertEqual(report.feedback_counts["disagree"], 1)
        self.assertEqual(report.feedback_counts["adjusted_invalidation"], 1)
        self.assertEqual(report.adjusted_invalidation_count, 2)
        self.assertEqual(report.median_user_invalidation_level, 70900.0)


if __name__ == "__main__":
    unittest.main()
