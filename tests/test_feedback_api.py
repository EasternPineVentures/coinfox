"""Feedback API, CLI, and storage contract tests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from coinfox.feedback import FeedbackEvent, FeedbackStore

try:
    from fastapi.testclient import TestClient

    from coinfox.api import app
except Exception:  # pragma: no cover - optional API extras may be absent
    TestClient = None
    app = None


class TestFeedbackContracts(unittest.TestCase):
    def test_storage_allows_anonymous_feedback_without_optional_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "feedback.sqlite"
            store = FeedbackStore(db)
            anonymous_id = str(uuid.uuid4())
            row_id = store.record(
                FeedbackEvent(
                    anonymous_user_id=anonymous_id,
                    symbol="BTCUSDT",
                    bias_shown="SHORT",
                    confidence_shown=0.71,
                    user_feedback="disagree",
                )
            )
            events = store.list_events(symbol="BTCUSDT")

        self.assertGreater(row_id, 0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].anonymous_user_id, anonymous_id)
        self.assertEqual(events[0].comment, "")
        self.assertNotIn("@", events[0].anonymous_user_id)

    def test_feedback_report_cli_returns_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "feedback.sqlite"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "coinfox",
                    "pulse",
                    "feedback-report",
                    "--db",
                    str(db),
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
            )
            payload = json.loads(result.stdout)

        self.assertEqual(payload["total_events"], 0)
        self.assertIn("feedback_counts", payload)
        self.assertIn("notes", payload)

    def test_feedback_api_accepts_valid_payload_and_rejects_missing_required_fields(self):
        if TestClient is None or app is None:
            self.skipTest("TODO: add FastAPI TestClient coverage when API extras are installed")

        client = TestClient(app)
        valid_payload = {
            "anonymous_user_id": str(uuid.uuid4()),
            "symbol": "BTCUSDT",
            "bias_shown": "SHORT",
            "confidence_shown": 0.71,
            "user_feedback": "disagree",
            "user_invalidation_level": 70800,
        }
        with patch("coinfox.api.record_feedback", return_value=123):
            ok = client.post("/feedback", json=valid_payload)
        missing = client.post("/feedback", json={"symbol": "BTCUSDT"})

        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["id"], 123)
        self.assertEqual(missing.status_code, 422)


if __name__ == "__main__":
    unittest.main()
