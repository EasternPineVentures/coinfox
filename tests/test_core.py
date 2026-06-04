"""Unit tests for indicators and trade-idea generator (pure, no network)."""

import math
import sqlite3
import tempfile
import unittest
from pathlib import Path

from coinfox.ai.churn import SCHEMA, _source_reliability_snapshot
from coinfox.community.arena import (
    Arena,
    ArenaError,
    BANKRUPTCY_RESCUE_FC,
    STARTING_BALANCE_FC,
    nyfe_timestamp,
)
from coinfox.data import Candle, FearGreed
from coinfox.indicators import bollinger, ema, macd, rsi, slope, volume_zscore
from coinfox.model import evaluate
from coinfox.trade import make_idea


def _synthetic_uptrend(n=120, start=20000.0, step=50.0):
    candles = []
    p = start
    for i in range(n):
        o = p
        c = p + step
        h = c + 10
        l = o - 5
        candles.append(Candle(i, o, h, l, c, 100.0, i + 1))
        p = c
    return candles
class TestIndicators(unittest.TestCase):
    def test_ema_constant(self):
        out = ema([10.0] * 50, 14)
        self.assertAlmostEqual(out[-1], 10.0, places=6)

    def test_rsi_uptrend_high(self):
        out = rsi(list(range(1, 100)), 14)
        self.assertGreater(out[-1], 70.0)

    def test_rsi_bounds(self):
        out = rsi([100 + (i % 5) for i in range(100)], 14)
        for v in out:
            if not math.isnan(v):
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 100.0)

    def test_macd_shapes(self):
        m = macd([100 + i * 0.1 for i in range(100)])
        self.assertEqual(len(m.hist), 100)

    def test_bollinger_pctb(self):
        bb = bollinger([100.0 + (i % 3) for i in range(50)], 20, 2.0)
        for v in bb.pct_b[20:]:
            self.assertFalse(math.isnan(v))

    def test_volume_zscore_constant(self):
        self.assertEqual(volume_zscore([5.0] * 30, 20)[-1], 0.0)

    def test_slope_positive(self):
        self.assertGreater(slope(list(range(1, 50)), 5), 0)


class TestModelAndTrade(unittest.TestCase):
    def test_uptrend_yields_long_bias(self):
        candles = _synthetic_uptrend()
        fng = FearGreed(50, "Neutral", 0)
        v = evaluate(candles, fng, horizon=4)
        # On a strong synthetic uptrend, we should never lean short.
        # (A perfect ramp pushes RSI to 100 and BB above upper, which
        # legitimately counter-balance trend signals — landing on
        # "long" or "neutral" is acceptable.)
        self.assertIn(v.bias, ("long", "neutral"))
        self.assertGreater(v.probability_up, 0.5)

    def test_trade_idea_long_setup(self):
        candles = _synthetic_uptrend()
        fng = FearGreed(50, "Neutral", 0)
        v = evaluate(candles, fng, horizon=4)
        idea = make_idea(v, candles, "1h")
        # On strong synthetic uptrend, we should get a LONG idea or at worst STAND ASIDE,
        # but never SHORT.
        self.assertIn(idea.action, ("LONG", "STAND ASIDE"))
        self.assertGreater(idea.entry, 0)
        self.assertGreaterEqual(idea.suggested_size_pct, 0.0)
        self.assertLessEqual(idea.suggested_size_pct, 2.0)  # cap

    def test_trade_idea_caps_size(self):
        candles = _synthetic_uptrend()
        fng = FearGreed(50, "Neutral", 0)
        v = evaluate(candles, fng, horizon=4)
        idea = make_idea(v, candles, "1h", kelly_cap_pct=0.5)
        self.assertLessEqual(idea.suggested_size_pct, 0.5)


class TestArena(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.arena = Arena(
            db_path=root / "community.sqlite",
            identity_path=root / "identity",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_user_gets_starting_balance_once(self):
        first = self.arena.ensure_user("FoxOne")
        second = self.arena.ensure_user("foxone")
        self.assertEqual(first.balance_fc, STARTING_BALANCE_FC)
        self.assertEqual(second.balance_fc, STARTING_BALANCE_FC)
        self.assertEqual(first.handle, "foxone")

    def test_profile_update_and_social_post_land_in_feed(self):
        profile = self.arena.update_profile("storyfox", display_name="Story Fox", bio="Looks for clean setups.")
        self.assertEqual(profile.display_name, "Story Fox")
        self.assertEqual(profile.bio, "Looks for clean setups.")

        post = self.arena.create_post("storyfox", "Watching BTC strength into the open.")
        self.assertEqual(post.author_handle, "storyfox")

        posts = self.arena.list_posts(handle="storyfox", limit=10)
        feed = self.arena.feed(limit=10)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].body, "Watching BTC strength into the open.")
        self.assertEqual(feed[0].event_type, "post")
        self.assertIn("Story Fox", feed[0].headline)

    def test_arena_activity_populates_feed(self):
        market_open_ts = nyfe_timestamp(2026, 6, 1, 10, 0)
        idea = self.arena.create_idea(
            author_handle="feedfox",
            title="BTC trend day",
            body="Momentum stays firm after open.",
            symbol="BTCUSDT",
            bias="long",
            resolution_rule="BTC closes above the session open.",
        )
        self.arena.open_position("feedfox", "BTCUSDT", "long", 50, now_ts=market_open_ts, price=100.0)
        events = self.arena.feed(limit=10, handle="feedfox")
        event_types = [event.event_type for event in events]
        self.assertIn("idea", event_types)
        self.assertIn("position_open", event_types)
        self.assertEqual(idea.author_handle, "feedfox")

    def test_idea_comment_bet_and_resolution_flow(self):
        self.arena.ensure_user("alpha")
        self.arena.ensure_user("beta")
        market_open_ts = nyfe_timestamp(2026, 6, 1, 10, 0)
        idea = self.arena.create_idea(
            author_handle="alpha",
            title="BTC squeezes higher",
            body="Funding stays calm and spot keeps leading.",
            symbol="BTCUSDT",
            bias="long",
            resolution_rule="BTC closes green on the next daily candle.",
        )
        comment = self.arena.add_comment(idea.id, "beta", "I think spot demand is real.")
        self.assertEqual(comment.idea_id, idea.id)

        self.arena.place_bet(idea.id, "alpha", "long", 100, now_ts=market_open_ts)
        self.arena.place_bet(idea.id, "beta", "short", 40, now_ts=market_open_ts)
        resolved = self.arena.resolve_idea(idea.id, "long", "alpha")

        self.assertEqual(resolved.status, "resolved")
        self.assertEqual(resolved.outcome, "long")
        self.assertEqual(self.arena.balance("alpha"), STARTING_BALANCE_FC + 40)
        self.assertEqual(self.arena.balance("beta"), STARTING_BALANCE_FC - 40)

    def test_bankruptcy_rescue_requires_zero_balance(self):
        """rescue() now delegates to borrow_gold(); second call blocked while loan is open."""
        self.arena.ensure_user("gamma")
        market_open_ts = nyfe_timestamp(2026, 6, 1, 10, 0)
        with self.assertRaises(ArenaError):
            self.arena.rescue("gamma")  # fails: non-zero balance

        idea = self.arena.create_idea(
            author_handle="gamma",
            title="BTC dumps",
            body="Momentum rolls over.",
            symbol="BTCUSDT",
            bias="short",
            resolution_rule="BTC closes red on the next daily candle.",
        )
        self.arena.place_bet(idea.id, "gamma", "long", STARTING_BALANCE_FC, now_ts=market_open_ts)
        self.arena.resolve_idea(idea.id, "short", "gamma")

        # Now at 0 balance — rescue() should succeed via loan
        rescued = self.arena.rescue("gamma")
        self.assertEqual(rescued.balance_fc, BANKRUPTCY_RESCUE_FC)
        # Second call blocked while loan is open
        with self.assertRaises(ArenaError):
            self.arena.rescue("gamma")

    def test_bets_require_market_hours(self):
        self.arena.ensure_user("delta")
        idea = self.arena.create_idea(
            author_handle="delta",
            title="BTC keeps trend",
            body="Trend holds through the session.",
            symbol="BTCUSDT",
            bias="long",
            resolution_rule="BTC closes green today.",
        )
        with self.assertRaises(ArenaError):
            self.arena.place_bet(idea.id, "delta", "long", 50, now_ts=nyfe_timestamp(2026, 6, 1, 8, 0))

    def test_position_open_and_exit_during_market_hours(self):
        position = self.arena.open_position(
            "trader",
            "BTCUSDT",
            "long",
            200,
            now_ts=nyfe_timestamp(2026, 6, 1, 10, 0),
            price=100.0,
        )
        self.assertEqual(self.arena.balance("trader"), STARTING_BALANCE_FC - 200)

        closed = self.arena.close_position(
            position.id,
            "trader",
            now_ts=nyfe_timestamp(2026, 6, 1, 11, 0),
            price=110.0,
        )
        self.assertEqual(closed.status, "closed")
        self.assertEqual(closed.realized_pnl_fc, 20)
        self.assertEqual(self.arena.balance("trader"), STARTING_BALANCE_FC + 20)

    def test_marked_positions_show_unrealized_pnl(self):
        self.arena.open_position(
            "markfox",
            "BTCUSDT",
            "long",
            150,
            now_ts=nyfe_timestamp(2026, 6, 1, 10, 0),
            price=100.0,
        )
        self.arena._price_fetcher = lambda symbol: 112.0
        marks = self.arena.marked_positions(handle="markfox", status="open", limit=10)
        self.assertEqual(len(marks), 1)
        self.assertEqual(marks[0].current_price, 112.0)
        self.assertEqual(marks[0].unrealized_pnl_fc, 18)
        self.assertEqual(marks[0].gross_value_fc, 168)

    def test_user_stats_aggregate_realized_and_unrealized(self):
        self.arena.open_position(
            "statfox",
            "BTCUSDT",
            "long",
            200,
            now_ts=nyfe_timestamp(2026, 6, 1, 10, 0),
            price=100.0,
        )
        losing = self.arena.open_position(
            "statfox",
            "ETHUSDT",
            "short",
            100,
            now_ts=nyfe_timestamp(2026, 6, 1, 10, 30),
            price=100.0,
        )
        self.arena.close_position(
            losing.id,
            "statfox",
            now_ts=nyfe_timestamp(2026, 6, 1, 11, 0),
            price=110.0,
        )
        self.arena._price_fetcher = lambda symbol: 105.0 if symbol == "BTCUSDT" else 110.0
        stats = self.arena.user_stats("statfox")
        self.assertEqual(stats.open_positions, 1)
        self.assertEqual(stats.closed_positions, 1)
        self.assertEqual(stats.winning_positions, 0)
        self.assertEqual(stats.losing_positions, 1)
        self.assertEqual(stats.realized_pnl_fc, -10)
        self.assertEqual(stats.unrealized_pnl_fc, 10)
        self.assertEqual(stats.total_staked_fc, 300)

    def test_position_open_rejected_outside_market_hours(self):
        with self.assertRaises(ArenaError):
            self.arena.open_position(
                "latefox",
                "BTCUSDT",
                "short",
                100,
                now_ts=nyfe_timestamp(2026, 6, 1, 18, 0),
                price=100.0,
            )

    def test_borrow_gold_only_at_zero_balance(self):
        """borrow_gold raises when balance > 0."""
        self.arena.ensure_user("borrowfox")
        with self.assertRaises(ArenaError):
            self.arena.borrow_gold("borrowfox", 500)

    def test_borrow_gold_full_flow(self):
        """Zero out, borrow, check balance, block second borrow, repay."""
        from coinfox.community.arena import LOAN_INTEREST_RATE, LOAN_MAX_GOLD
        market_open_ts = nyfe_timestamp(2026, 6, 1, 10, 0)
        idea = self.arena.create_idea(
            author_handle="loanfox",
            title="test idea",
            body="Testing loan flow.",
            symbol="BTCUSDT",
            bias="long",
            resolution_rule="Closes green.",
        )
        self.arena.place_bet(idea.id, "loanfox", "long", STARTING_BALANCE_FC, now_ts=market_open_ts)
        self.arena.resolve_idea(idea.id, "short", "loanfox")
        self.assertEqual(self.arena.balance("loanfox"), 0)

        loan = self.arena.borrow_gold("loanfox", 400)
        self.assertEqual(loan.principal_fc, 400)
        self.assertEqual(loan.interest_fc, int(round(400 * LOAN_INTEREST_RATE)))
        self.assertEqual(loan.status, "open")
        self.assertEqual(self.arena.balance("loanfox"), 400)

        # second borrow blocked
        with self.assertRaises(ArenaError):
            self.arena.borrow_gold("loanfox", 100)

        # repay
        total_owed = loan.principal_fc + loan.interest_fc
        # top up so user can repay
        conn = self.arena._connect()
        conn.execute(
            "INSERT INTO wallet_ledger(handle, delta_fc, reason, created_ts) VALUES(?,?,?,?)",
            ("loanfox", total_owed - 400, "test_topup", int(__import__("time").time())),
        )
        conn.commit()
        conn.close()
        repaid = self.arena.repay_gold("loanfox")
        self.assertEqual(repaid.status, "repaid")
        self.assertIsNone(self.arena.open_loan("loanfox"))

    def test_borrow_gold_capped_at_max(self):
        """Borrowing more than LOAN_MAX_GOLD is silently capped."""
        from coinfox.community.arena import LOAN_MAX_GOLD
        market_open_ts = nyfe_timestamp(2026, 6, 1, 10, 0)
        idea = self.arena.create_idea(
            author_handle="capfox",
            title="cap test",
            body="Cap test.",
            symbol="BTCUSDT",
            bias="long",
            resolution_rule="Closes green.",
        )
        self.arena.place_bet(idea.id, "capfox", "long", STARTING_BALANCE_FC, now_ts=market_open_ts)
        self.arena.resolve_idea(idea.id, "short", "capfox")
        loan = self.arena.borrow_gold("capfox", LOAN_MAX_GOLD + 9999)
        self.assertLessEqual(loan.principal_fc, LOAN_MAX_GOLD)


class TestChurnReliability(unittest.TestCase):
    def test_source_reliability_snapshot_returns_smoothed_scores(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        # Two past digests: one full success, one with explicit failures.
        conn.execute(
            "INSERT INTO thoughts (ts, bias, conviction, headline, body, provider, model, cost_tier, digest) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "long",
                3,
                "h1",
                "b1",
                "p",
                "m",
                "free",
                '{"source_status":{"prices":"ok","global_market":"ok","derivatives":"ok","onchain":"ok","news":"ok","social":"ok","dev":"ok","macro":"ok","sentiment":"ok"}}',
            ),
        )
        conn.execute(
            "INSERT INTO thoughts (ts, bias, conviction, headline, body, provider, model, cost_tier, digest) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                2,
                "neutral",
                2,
                "h2",
                "b2",
                "p",
                "m",
                "free",
                '{"source_status":{"prices":"ok","global_market":"error","derivatives":"error","onchain":"ok","news":"ok","social":"ok","dev":"ok","macro":"ok","sentiment":"ok"}}',
            ),
        )

        current = {
            "source_status": {
                "prices": "ok",
                "global_market": "error",
                "derivatives": "ok",
                "onchain": "ok",
                "news": "ok",
                "social": "ok",
                "dev": "ok",
                "macro": "ok",
                "sentiment": "ok",
            }
        }
        snap = _source_reliability_snapshot(conn, current)
        self.assertEqual(snap["sample_size"], 2)
        self.assertIn("global_market", snap["current_errors"])
        self.assertAlmostEqual(snap["per_source"]["prices"], 0.75, places=4)
        self.assertAlmostEqual(snap["per_source"]["global_market"], 0.5, places=4)
        self.assertEqual(snap["weakest_source"], "global_market")
        conn.close()

    def test_source_reliability_snapshot_handles_missing_status(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        snap = _source_reliability_snapshot(conn, {"foo": "bar"})
        self.assertEqual(snap["sample_size"], 0)
        self.assertEqual(snap["overall"], 0.0)
        self.assertEqual(snap["per_source"], {})
        conn.close()


if __name__ == "__main__":
    unittest.main()
