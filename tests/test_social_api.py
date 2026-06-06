"""Social store + mobile-facing API contract tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from coinfox.community.social import SocialError, SocialStore

try:
    from fastapi.testclient import TestClient

    from coinfox.api import app
except Exception:  # pragma: no cover - optional API extras may be absent
    TestClient = None
    app = None


VALID_DRAFT = {
    "symbol": "btcusdt",
    "direction": "long",
    "entry_price": 100.0,
    "stop_loss": 90.0,
    "take_profit": 130.0,
    "reasoning": "reclaimed support",
}


class TestSocialStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = SocialStore(Path(self._tmp.name) / "social.sqlite")

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_user_grants_starting_gold_and_blocks_duplicates(self):
        user = self.store.create_user("@Brooklyn")
        self.assertEqual(user["username"], "Brooklyn")
        self.assertEqual(user["gold"], 500)
        self.assertEqual(user["total_predictions"], 0)
        with self.assertRaises(SocialError):
            self.store.create_user("Brooklyn")

    def test_post_normalizes_symbol_and_rejects_bad_levels(self):
        user = self.store.create_user("trader")
        post = self.store.create_post(user["id"], VALID_DRAFT)
        self.assertEqual(post["symbol"], "BTCUSDT")
        self.assertEqual(post["direction"], "long")
        self.assertEqual(post["user"]["id"], user["id"])
        self.assertEqual(post["prediction_stats"], {"tp_predictions": 0, "sl_predictions": 0})
        self.assertIsNone(post["user_prediction"])
        with self.assertRaises(SocialError):
            self.store.create_post(user["id"], {**VALID_DRAFT, "entry_price": 0})
        with self.assertRaises(SocialError):
            self.store.create_post(user["id"], {**VALID_DRAFT, "direction": "sideways"})

    def test_predictions_count_and_are_one_per_user(self):
        author = self.store.create_user("author")
        caller = self.store.create_user("caller")
        post = self.store.create_post(author["id"], VALID_DRAFT)

        self.store.predict(caller["id"], post["id"], "tp_hit")
        with self.assertRaises(SocialError):
            self.store.predict(caller["id"], post["id"], "sl_hit")

        # viewer sees their own pick; stats reflect the single call
        viewed = self.store.get_post(post["id"], viewer_id=caller["id"])
        self.assertEqual(viewed["user_prediction"], "tp_hit")
        self.assertEqual(viewed["prediction_stats"]["tp_predictions"], 1)
        self.assertEqual(self.store.get_user(caller["id"])["total_predictions"], 1)

        # a different viewer has no pick recorded
        other = self.store.get_post(post["id"], viewer_id=author["id"])
        self.assertIsNone(other["user_prediction"])

    def test_comments_round_trip_with_author(self):
        author = self.store.create_user("poster")
        post = self.store.create_post(author["id"], VALID_DRAFT)
        commenter = self.store.create_user("replier")
        saved = self.store.add_comment(commenter["id"], post["id"], "nice level")
        self.assertEqual(saved["content"], "nice level")
        self.assertEqual(saved["user"]["username"], "replier")
        listed = self.store.list_comments(post["id"])
        self.assertEqual([c["content"] for c in listed], ["nice level"])

    def test_list_posts_is_newest_first(self):
        user = self.store.create_user("seq")
        first = self.store.create_post(user["id"], {**VALID_DRAFT, "symbol": "SPY"})
        second = self.store.create_post(user["id"], {**VALID_DRAFT, "symbol": "QQQ"})
        ids = [p["id"] for p in self.store.list_posts(limit=10)]
        self.assertEqual(ids[0], second["id"])
        self.assertIn(first["id"], ids)


@unittest.skipIf(TestClient is None or app is None, "FastAPI extras not installed")
class TestSocialApi(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        store = SocialStore(Path(self._tmp.name) / "social.sqlite")
        self._patch = patch("coinfox.api._SOCIAL", store)
        self._patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_full_social_flow(self):
        user = self.client.post("/api/users", json={"username": "alpha"})
        self.assertEqual(user.status_code, 200)
        uid = user.json()["id"]

        headers = {"x-user-id": uid}
        created = self.client.post("/api/posts", json=VALID_DRAFT, headers=headers)
        self.assertEqual(created.status_code, 200)
        post_id = created.json()["id"]

        listed = self.client.get("/api/posts", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)

        predicted = self.client.post(
            f"/api/posts/{post_id}/predict",
            json={"predicted_outcome": "tp_hit"},
            headers=headers,
        )
        self.assertEqual(predicted.status_code, 200)

        commented = self.client.post(
            f"/api/posts/{post_id}/comments",
            json={"content": "agreed"},
            headers=headers,
        )
        self.assertEqual(commented.status_code, 200)
        comments = self.client.get(f"/api/posts/{post_id}/comments")
        self.assertEqual(comments.json()[0]["content"], "agreed")

    def test_mutations_require_user_header(self):
        missing = self.client.post("/api/posts", json=VALID_DRAFT)
        self.assertEqual(missing.status_code, 401)

    def test_feed_broadcasts_new_post(self):
        uid = self.client.post("/api/users", json={"username": "broadcaster"}).json()["id"]
        with self.client.websocket_connect("/ws/feed") as ws:
            self.client.post("/api/posts", json=VALID_DRAFT, headers={"x-user-id": uid})
            message = ws.receive_json()
        self.assertEqual(message["type"], "new_post")
        self.assertEqual(message["user_id"], uid)


if __name__ == "__main__":
    unittest.main()
