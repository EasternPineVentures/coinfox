"""Social store + mobile-facing API contract tests."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from coinfox.community.social import POST_TTL_HOURS, SocialError, SocialStore

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

    def test_boost_and_fade_move_score_and_reputation(self):
        author = self.store.create_user("author")
        a = self.store.create_user("voter_a")
        b = self.store.create_user("voter_b")
        post = self.store.create_post(author["id"], VALID_DRAFT)

        self.store.vote(a["id"], post["id"], "boost")
        self.store.vote(b["id"], post["id"], "boost")
        viewed = self.store.get_post(post["id"], viewer_id=a["id"])
        self.assertEqual(viewed["score"], 2)
        self.assertEqual(viewed["viewer_vote"], "boost")
        self.assertEqual(self.store.get_user(author["id"])["reputation"], 2)

        # B switches a boost to a fade: score 2 -> 0, reputation 2 -> 0.
        self.store.vote(b["id"], post["id"], "fade")
        self.assertEqual(self.store.get_post(post["id"])["score"], 0)
        self.assertEqual(self.store.get_user(author["id"])["reputation"], 0)

        # A clears their boost: score 0 -> -1.
        self.store.vote(a["id"], post["id"], "clear")
        viewed = self.store.get_post(post["id"], viewer_id=a["id"])
        self.assertEqual(viewed["score"], -1)
        self.assertIsNone(viewed["viewer_vote"])
        self.assertEqual(self.store.get_user(author["id"])["reputation"], -1)

    def test_vote_rejects_bad_direction(self):
        author = self.store.create_user("seller")
        post = self.store.create_post(author["id"], VALID_DRAFT)
        with self.assertRaises(SocialError):
            self.store.vote(author["id"], post["id"], "sideways")

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

    def test_boost_endpoint_updates_score(self):
        author = self.client.post("/api/users", json={"username": "writer"}).json()
        voter = self.client.post("/api/users", json={"username": "fan"}).json()
        post_id = self.client.post(
            "/api/posts", json=VALID_DRAFT, headers={"x-user-id": author["id"]}
        ).json()["id"]

        boosted = self.client.post(
            f"/api/posts/{post_id}/vote",
            json={"direction": "boost"},
            headers={"x-user-id": voter["id"]},
        )
        self.assertEqual(boosted.status_code, 200, boosted.text)
        self.assertEqual(boosted.json()["score"], 1)
        self.assertEqual(boosted.json()["viewer_vote"], "boost")

        # Author's reputation (shown as Cred) rose.
        self.assertEqual(self.client.get(f"/api/users/{author['id']}").json()["reputation"], 1)

    def test_mutations_require_user_header(self):
        missing = self.client.post("/api/posts", json=VALID_DRAFT)
        self.assertEqual(missing.status_code, 401)

    def test_vote_broadcasts_live_score(self):
        author = self.client.post("/api/users", json={"username": "writer2"}).json()
        voter = self.client.post("/api/users", json={"username": "fan2"}).json()
        post_id = self.client.post(
            "/api/posts", json=VALID_DRAFT, headers={"x-user-id": author["id"]}
        ).json()["id"]
        with self.client.websocket_connect("/ws/feed") as ws:
            self.client.post(
                f"/api/posts/{post_id}/vote",
                json={"direction": "boost"},
                headers={"x-user-id": voter["id"]},
            )
            message = ws.receive_json()
        self.assertEqual(message["type"], "new_vote")
        self.assertEqual(message["post_id"], post_id)
        self.assertEqual(message["score"], 1)

    def test_feed_broadcasts_new_post(self):
        uid = self.client.post("/api/users", json={"username": "broadcaster"}).json()["id"]
        with self.client.websocket_connect("/ws/feed") as ws:
            self.client.post("/api/posts", json=VALID_DRAFT, headers={"x-user-id": uid})
            message = ws.receive_json()
        self.assertEqual(message["type"], "new_post")
        self.assertEqual(message["user_id"], uid)


class TestProofRankedFeed(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = SocialStore(Path(self._tmp.name) / "social.sqlite")

    def tearDown(self):
        self._tmp.cleanup()

    def _post(self, author_id, **overrides):
        draft = dict(VALID_DRAFT)
        draft.update(overrides)
        return self.store.create_post(author_id, draft)["id"]

    def test_resolve_post_credits_correct_predictors(self):
        author = self.store.create_user("author")
        right = self.store.create_user("right_caller")
        wrong = self.store.create_user("wrong_caller")
        post_id = self._post(author["id"])
        self.store.predict(right["id"], post_id, "tp_hit")
        self.store.predict(wrong["id"], post_id, "sl_hit")

        resolved = self.store.resolve_post(post_id, "tp_hit")
        self.assertTrue(resolved["resolved"])
        self.assertEqual(resolved["outcome"], "tp_hit")
        self.assertEqual(self.store.get_user(right["id"])["correct_predictions"], 1)
        self.assertEqual(self.store.get_user(wrong["id"])["correct_predictions"], 0)
        with self.assertRaises(SocialError):
            self.store.resolve_post(post_id, "tp_hit")  # no double-resolve

    def test_track_record_reflects_call_outcomes(self):
        author = self.store.create_user("proven")
        for outcome in ("tp_hit", "tp_hit", "sl_hit"):
            self.store.resolve_post(self._post(author["id"]), outcome)

        record = self.store.author_track_record(author["id"])
        self.assertEqual(record["resolved_calls"], 3)
        self.assertEqual(record["winning_calls"], 2)
        self.assertAlmostEqual(record["call_win_rate"], 2 / 3, places=4)
        self.assertGreater(record["credibility"], 1.0)

    def test_feed_ranks_proven_author_above_fresh_unknown(self):
        proven = self.store.create_user("proven")
        rookie = self.store.create_user("rookie")
        for _ in range(6):
            self.store.resolve_post(self._post(proven["id"]), "tp_hit")

        proven_post = self._post(proven["id"], reasoning="full thesis " * 6)
        rookie_post = self._post(rookie["id"])  # newest, but unproven & thin

        ranked = self.store.list_feed_ranked(limit=10)
        ids = [p["id"] for p in ranked]
        self.assertLess(ids.index(proven_post), ids.index(rookie_post))
        self.assertIn("rank_score", ranked[0])
        self.assertIn("credibility", ranked[0]["track_record"])

    def test_resolve_open_posts_closes_on_price(self):
        author = self.store.create_user("author")
        # long: entry 100, stop 90, target 130
        winner = self._post(author["id"])
        loser = self._post(author["id"], direction="short", take_profit=80.0)

        summary = self.store.resolve_open_posts(lambda sym: 135.0)
        outcomes = {r["post_id"]: r["outcome"] for r in summary["resolved"]}
        self.assertEqual(outcomes[winner], "tp_hit")   # long hit target
        self.assertEqual(outcomes[loser], "sl_hit")    # short stopped out

    def test_resolve_open_posts_expires_stale_undecided(self):
        author = self.store.create_user("author")
        post_id = self._post(author["id"])
        # Price sits between stop and target → not decided; force TTL elapsed.
        future = time.time() + POST_TTL_HOURS * 3600 + 60
        summary = self.store.resolve_open_posts(lambda sym: 110.0, now=future)
        self.assertIn(post_id, summary["expired"])
        self.assertEqual(self.store.get_post(post_id)["outcome"], "expired")

    def test_resolve_open_posts_survives_flaky_feed(self):
        author = self.store.create_user("author")
        self._post(author["id"])

        def boom(sym):
            raise RuntimeError("feed down")

        summary = self.store.resolve_open_posts(boom)  # must not raise
        self.assertEqual(summary["resolved"], [])

    def test_discussion_post_has_no_levels_and_rides_the_feed(self):
        author = self.store.create_user("talker")
        disc = self.store.create_discussion(
            author["id"],
            {"title": "Are we pricing in too many rate cuts?", "body": "Curious what people think.", "topic": "macro"},
        )
        self.assertEqual(disc["kind"], "discussion")
        self.assertEqual(disc["title"], "Are we pricing in too many rate cuts?")
        self.assertEqual(disc["symbol"], "MACRO")  # topic tag, uppercased
        # It shows up in the feed alongside calls.
        ids = [p["id"] for p in self.store.list_feed_ranked(limit=10)]
        self.assertIn(disc["id"], ids)

    def test_discussion_cannot_be_predicted_or_resolved(self):
        author = self.store.create_user("talker2")
        voter = self.store.create_user("voter2")
        disc = self.store.create_discussion(author["id"], {"title": "Wolf of Wall St rewatch thread"})
        with self.assertRaises(SocialError):
            self.store.predict(voter["id"], disc["id"], "tp_hit")
        with self.assertRaises(SocialError):
            self.store.resolve_post(disc["id"], "tp_hit")
        # But it CAN be voted on like anything else.
        self.assertEqual(self.store.vote(voter["id"], disc["id"], "boost")["score"], 1)

    def test_resolver_ignores_discussions(self):
        author = self.store.create_user("talker3")
        disc = self.store.create_discussion(author["id"], {"title": "General chat"})
        # Even far in the future, a discussion never expires/resolves.
        summary = self.store.resolve_open_posts(lambda s: 100.0, now=time.time() + 10**9)
        self.assertNotIn(disc["id"], summary["expired"])
        self.assertFalse(self.store.get_post(disc["id"])["resolved"])

    def test_oauth_find_or_create_is_stable(self):
        first = self.store.find_or_create_oauth_user("google", "sub-123", email="ada@example.com")
        again = self.store.find_or_create_oauth_user("google", "sub-123", email="ada@example.com")
        self.assertEqual(first["id"], again["id"])  # same identity -> same account
        self.assertEqual(first["username"], "ada")

        # A different person who'd collide on handle gets a unique one.
        other = self.store.find_or_create_oauth_user("google", "sub-999", email="ada@other.com")
        self.assertNotEqual(other["id"], first["id"])
        self.assertEqual(other["username"], "ada1")

    def test_comment_voting_sorts_and_surfaces_top(self):
        author = self.store.create_user("op")
        a = self.store.create_user("voice_a")
        b = self.store.create_user("voice_b")
        crowd = [self.store.create_user(f"c{i}") for i in range(3)]
        post_id = self._post(author["id"])
        c_meh = self.store.add_comment(a["id"], post_id, "meh, I'd fade this")
        c_great = self.store.add_comment(b["id"], post_id, "great level, watching for the reclaim")

        # The crowd lifts the second take.
        for u in crowd:
            self.store.vote_comment(u["id"], c_great["id"], "boost")
        self.store.vote_comment(a["id"], c_meh["id"], "fade")

        ranked = self.store.list_comments(post_id, viewer_id=a["id"])
        self.assertEqual(ranked[0]["content"], "great level, watching for the reclaim")
        self.assertEqual(ranked[0]["score"], 3)
        self.assertEqual(ranked[1]["score"], -1)
        self.assertEqual(ranked[1]["viewer_vote"], "fade")  # viewer's own vote echoed

        # The best take is surfaced on the post card itself.
        feed = self.store.list_feed_ranked(limit=10)
        card = next(p for p in feed if p["id"] == post_id)
        self.assertEqual(card["comment_count"], 2)
        self.assertEqual(card["top_comment"]["content"], "great level, watching for the reclaim")
        self.assertEqual(card["top_comment"]["score"], 3)

    def test_resolved_calls_leave_the_feed(self):
        author = self.store.create_user("author")
        resolved = self._post(author["id"])
        self.store.resolve_post(resolved, "tp_hit")  # proven, but no longer actionable
        open_call = self._post(author["id"])  # fresh, still actionable

        ids = [p["id"] for p in self.store.list_feed_ranked(limit=10)]
        self.assertIn(open_call, ids)
        self.assertNotIn(resolved, ids)  # its proof lives on the author badge

    def test_boost_lifts_ranking(self):
        author = self.store.create_user("author")
        voter = self.store.create_user("voter")
        low = self._post(author["id"])
        high = self._post(author["id"])
        self.store.vote(voter["id"], high, "boost")

        ranked = self.store.list_feed_ranked(limit=10)
        ids = [p["id"] for p in ranked]
        self.assertLess(ids.index(high), ids.index(low))


@unittest.skipIf(TestClient is None, "fastapi not installed")
class TestFeedApi(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = patch(
            "coinfox.api._SOCIAL", SocialStore(Path(self._tmp.name) / "social.sqlite")
        )
        self._patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_ranked_feed_and_track_record_endpoints(self):
        uid = self.client.post("/api/users", json={"username": "trader"}).json()["id"]
        self.client.post("/api/posts", json=VALID_DRAFT, headers={"x-user-id": uid})

        feed = self.client.get("/api/feed")
        self.assertEqual(feed.status_code, 200, feed.text)
        self.assertEqual(len(feed.json()), 1)
        self.assertIn("rank_score", feed.json()[0])

        record = self.client.get(f"/api/users/{uid}/track-record")
        self.assertEqual(record.status_code, 200, record.text)
        self.assertIn("credibility", record.json())


if __name__ == "__main__":
    unittest.main()
