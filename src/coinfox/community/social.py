"""Self-contained social store powering the CoinFox mobile feed.

This backs the mobile app's public contract exactly (see ``mobile/src/types.ts``):
``User``, ``TradePost``, ``Comment`` and ``tp_hit`` / ``sl_hit`` predictions.

It is intentionally separate from :mod:`coinfox.community.arena` (the play-money
"NY Fox Exchange" game, which uses a different Idea/Bet schema). Keeping the two
apart means the mobile feed gets a backend shaped like the screens that consume
it, while the arena remains its own product surface.

Storage is a local SQLite file (``~/.coinfox/social.sqlite`` by default, override
with the ``COINFOX_SOCIAL_DB`` environment variable).
"""

from __future__ import annotations

import math
import os
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

# Mirror the arena's starting Gold so the two economies feel consistent.
STARTING_GOLD = 500
DEFAULT_TRUST_LEVEL = 1
POST_TTL_HOURS = 24
VALID_DIRECTIONS = {"long", "short"}
VALID_OUTCOMES = {"tp_hit", "sl_hit"}
POST_KIND_CALL = "call"
POST_KIND_DISCUSSION = "discussion"
DISCUSSION_TITLE_MAX = 160
DISCUSSION_BODY_MAX = 5000


class SocialError(ValueError):
    """Raised when a social action cannot be completed."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id                   TEXT PRIMARY KEY,
    username             TEXT NOT NULL UNIQUE,
    gold                 INTEGER NOT NULL,
    total_predictions    INTEGER NOT NULL DEFAULT 0,
    correct_predictions  INTEGER NOT NULL DEFAULT 0,
    trust_level          INTEGER NOT NULL DEFAULT 1,
    reputation           INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
    id              TEXT PRIMARY KEY,
    author_id       TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'call',
    title           TEXT,
    body            TEXT,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,
    entry_price     REAL NOT NULL,
    stop_loss       REAL NOT NULL,
    take_profit     REAL NOT NULL,
    reasoning       TEXT,
    chart_image_url TEXT,
    foxtrot_score   REAL,
    regime          TEXT,
    confidence      REAL,
    resolved        INTEGER NOT NULL DEFAULT 0,
    outcome         TEXT,
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    created_ts      INTEGER NOT NULL,
    FOREIGN KEY(author_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_ts DESC);
CREATE TABLE IF NOT EXISTS predictions (
    id          TEXT PRIMARY KEY,
    post_id     TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    outcome     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(post_id, user_id),
    FOREIGN KEY(post_id) REFERENCES posts(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_predictions_post ON predictions(post_id);
CREATE TABLE IF NOT EXISTS comments (
    id          TEXT PRIMARY KEY,
    post_id     TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    created_ts  INTEGER NOT NULL,
    FOREIGN KEY(post_id) REFERENCES posts(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, created_ts ASC);
CREATE TABLE IF NOT EXISTS votes (
    id          TEXT PRIMARY KEY,
    post_id     TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    value       INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(post_id, user_id),
    FOREIGN KEY(post_id) REFERENCES posts(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_votes_post ON votes(post_id);
CREATE TABLE IF NOT EXISTS comment_votes (
    id          TEXT PRIMARY KEY,
    comment_id  TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    value       INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(comment_id, user_id),
    FOREIGN KEY(comment_id) REFERENCES comments(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_comment_votes ON comment_votes(comment_id);
CREATE TABLE IF NOT EXISTS auth_identities (
    id                TEXT PRIMARY KEY,
    provider          TEXT NOT NULL,
    provider_user_id  TEXT NOT NULL,
    email             TEXT,
    user_id           TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    UNIQUE(provider, provider_user_id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_auth_identities_user ON auth_identities(user_id);
"""

# Boost = upvote (+1), Fade = downvote (-1). "clear" removes an existing vote.
VOTE_VALUES = {"boost": 1, "fade": -1}

# --- Proof-ranked feed tunables -------------------------------------------
# The FYP engine surfaces the people who are actually *right*, not just loud.
# Ranking blends: author credibility (call outcomes + reputation + Gold) x
# freshness x vote score x thesis quality x this post's own resolution.
RANK_HALFLIFE_HOURS = 12.0   # a post's freshness weight halves every 12h
RANK_PRIOR_CALLS = 5         # Bayesian prior strength for a new author's win rate
RANK_PRIOR_WINRATE = 0.5     # assume neutral 50% until an author proves otherwise
RANK_VOTE_WEIGHT = 0.15      # each net Boost adds 15% to a post's weight
RANK_THESIS_MIN_LEN = 40     # reasoning longer than this counts as a real thesis
RANK_THESIS_BONUS = 1.15
RANK_ENGAGEMENT_WEIGHT = 0.05  # mild lift per crowd call (tp/sl prediction)
RANK_RESOLVED_SINK = 0.1       # resolved calls sink below every open call


def _freshness_factor(age_hours: float) -> float:
    """Exponential time decay so the feed stays alive without burying proof."""
    return 0.5 ** (max(0.0, float(age_hours)) / RANK_HALFLIFE_HOURS)


def _credibility(smoothed_win_rate: float, reputation: int, gold: int) -> float:
    """Collapse an author's track record into a single ranking multiplier.

    Centred on ~1.0 for an unproven author. A proven winner with reputation and
    arena Gold lifts above 1.0; a proven loser sinks below. Clamped so no single
    account can dominate the feed."""
    win_component = 0.5 + float(smoothed_win_rate)            # 0.5 .. 1.5
    rep_component = 1.0 + 0.05 * math.log1p(max(0, reputation))
    gold_component = 1.0 + 0.0002 * (int(gold) - STARTING_GOLD)
    value = win_component * rep_component * gold_component
    return max(0.25, min(2.5, value))


def _evaluate_outcome(
    direction: str, price: float, stop_loss: float, take_profit: float
) -> Optional[str]:
    """Decide whether a live price has closed a call. Returns 'tp_hit',
    'sl_hit', or None if the call is still open. If both levels are crossed
    (a gap), the stop is honoured first — the conservative read."""
    direction = str(direction).strip().lower()
    price = float(price)
    if direction == "long":
        if price <= float(stop_loss):
            return "sl_hit"
        if price >= float(take_profit):
            return "tp_hit"
    elif direction == "short":
        if price >= float(stop_loss):
            return "sl_hit"
        if price <= float(take_profit):
            return "tp_hit"
    return None


def _rank_score(
    *,
    credibility: float,
    age_hours: float,
    vote_score: int,
    has_thesis: bool,
    crowd_calls: int,
    outcome: Optional[str],
) -> float:
    """Blend the ranking signals into a single sortable score.

    score = credibility x freshness x votes x thesis x engagement x resolution
    Multiplicative so a strong author with a fresh, well-argued, well-voted call
    rises, while a faded or stale post sinks."""
    vote_factor = max(0.1, 1.0 + RANK_VOTE_WEIGHT * int(vote_score))
    thesis_factor = RANK_THESIS_BONUS if has_thesis else 1.0
    engagement_factor = 1.0 + RANK_ENGAGEMENT_WEIGHT * max(0, int(crowd_calls))
    # The feed is for live, actionable calls. Once a call resolves it drops down
    # hard — its proof lives on the author's track-record badge, not by crowding
    # the top of the feed with trades nobody can take anymore.
    resolution_factor = 1.0 if not outcome else RANK_RESOLVED_SINK
    return (
        float(credibility)
        * _freshness_factor(age_hours)
        * vote_factor
        * thesis_factor
        * engagement_factor
        * resolution_factor
    )


def _iso(ts: Optional[float] = None) -> str:
    moment = datetime.fromtimestamp(ts, tz=timezone.utc) if ts is not None else datetime.now(timezone.utc)
    return moment.isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return uuid.uuid4().hex


def _iso_to_ts(value: str) -> float:
    """Parse an ISO string written by :func:`_iso` back to a UNIX timestamp."""
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()


class SocialStore:
    """SQLite-backed store for users, trade posts, comments and predictions."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)
            # Migrate older DBs that predate the reputation column.
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            if "reputation" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN reputation INTEGER NOT NULL DEFAULT 0")
            # Migrate older DBs that predate free-form discussion posts.
            post_columns = {row["name"] for row in conn.execute("PRAGMA table_info(posts)")}
            if "kind" not in post_columns:
                conn.execute("ALTER TABLE posts ADD COLUMN kind TEXT NOT NULL DEFAULT 'call'")
            if "title" not in post_columns:
                conn.execute("ALTER TABLE posts ADD COLUMN title TEXT")
            if "body" not in post_columns:
                conn.execute("ALTER TABLE posts ADD COLUMN body TEXT")

    # ------------------------------------------------------------------ users
    def create_user(self, username: str) -> dict:
        handle = _normalize_username(username)
        now = time.time()
        user_id = _new_id()
        with closing(self._connect()) as conn, conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (handle,)
            ).fetchone()
            if existing is not None:
                raise SocialError(f"username '{handle}' is taken")
            conn.execute(
                "INSERT INTO users(id, username, gold, total_predictions, "
                "correct_predictions, trust_level, created_at) VALUES(?,?,?,?,?,?,?)",
                (user_id, handle, STARTING_GOLD, 0, 0, DEFAULT_TRUST_LEVEL, _iso(now)),
            )
        return self.get_user(user_id)

    def get_user(self, user_id: str) -> dict:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise SocialError("user not found")
        return _user_dict(row)

    def find_or_create_oauth_user(
        self,
        provider: str,
        provider_user_id: str,
        email: Optional[str] = None,
        suggested_username: Optional[str] = None,
    ) -> dict:
        """Resolve a social login to a CoinFox account. If we've seen this
        provider identity before, return its user; otherwise create a fresh
        account with a unique handle and link the identity. Provider-agnostic,
        so Google/Apple/GitHub/etc. all flow through here."""
        provider = str(provider).strip().lower()
        provider_user_id = str(provider_user_id).strip()
        if not provider or not provider_user_id:
            raise SocialError("provider identity is required")
        now = time.time()
        with closing(self._connect()) as conn, conn:
            existing = conn.execute(
                "SELECT user_id FROM auth_identities WHERE provider = ? AND provider_user_id = ?",
                (provider, provider_user_id),
            ).fetchone()
            if existing is not None:
                user_id = existing["user_id"]
            else:
                base = suggested_username or (email.split("@")[0] if email else "trader")
                username = self._unique_username(conn, base)
                user_id = _new_id()
                conn.execute(
                    "INSERT INTO users(id, username, gold, total_predictions, "
                    "correct_predictions, trust_level, reputation, created_at) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (user_id, username, STARTING_GOLD, 0, 0, DEFAULT_TRUST_LEVEL, 0, _iso(now)),
                )
                conn.execute(
                    "INSERT INTO auth_identities(id, provider, provider_user_id, email, user_id, created_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (_new_id(), provider, provider_user_id, email, user_id, _iso(now)),
                )
        return self.get_user(user_id)

    def _unique_username(self, conn: sqlite3.Connection, base: str) -> str:
        handle = _normalize_username(str(base) or "trader")[:32] or "trader"
        candidate = handle
        suffix = 0
        while conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (candidate,)
        ).fetchone() is not None:
            suffix += 1
            candidate = f"{handle}{suffix}"
        return candidate

    # ------------------------------------------------------------------ posts
    def create_post(self, user_id: str, draft: dict) -> dict:
        self._require_user(user_id)
        symbol = str(draft.get("symbol", "")).strip().upper()
        if not symbol:
            raise SocialError("symbol is required")
        direction = str(draft.get("direction", "")).strip().lower()
        if direction not in VALID_DIRECTIONS:
            raise SocialError("direction must be 'long' or 'short'")
        entry = _positive_number(draft.get("entry_price"), "entry_price")
        stop = _positive_number(draft.get("stop_loss"), "stop_loss")
        target = _positive_number(draft.get("take_profit"), "take_profit")

        now = time.time()
        post_id = _new_id()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO posts(id, author_id, kind, symbol, direction, entry_price, "
                "stop_loss, take_profit, reasoning, chart_image_url, foxtrot_score, "
                "regime, confidence, resolved, outcome, created_at, expires_at, created_ts) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    post_id,
                    user_id,
                    POST_KIND_CALL,
                    symbol,
                    direction,
                    entry,
                    stop,
                    target,
                    _clean_optional_text(draft.get("reasoning")),
                    _clean_optional_text(draft.get("chart_image_url")),
                    _optional_number(draft.get("foxtrot_score")),
                    _clean_optional_text(draft.get("regime")),
                    _optional_number(draft.get("confidence")),
                    0,
                    None,
                    _iso(now),
                    _iso(now + POST_TTL_HOURS * 3600),
                    int(now),
                ),
            )
        return self.get_post(post_id, viewer_id=user_id)

    def create_discussion(self, user_id: str, draft: dict) -> dict:
        """Create a free-form discussion post — title + body, no trade levels.
        Trading is the foundation, but people come here to talk: macro, the Fed,
        a thesis, or just the vibe. These ride the same feed/vote/comment rails
        as calls; they simply never resolve. An optional ``topic`` tag (often a
        symbol like BTC, or MACRO/FED) helps people filter."""
        self._require_user(user_id)
        title = str(draft.get("title", "")).strip()
        if not title:
            raise SocialError("title is required")
        if len(title) > DISCUSSION_TITLE_MAX:
            raise SocialError("title is too long")
        body = str(draft.get("body", "") or "").strip()
        if len(body) > DISCUSSION_BODY_MAX:
            raise SocialError("body is too long")
        # 'symbol' doubles as a topic tag for discussions (stored, never priced).
        topic = str(draft.get("topic", "") or "").strip().upper()

        now = time.time()
        post_id = _new_id()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO posts(id, author_id, kind, title, body, symbol, direction, "
                "entry_price, stop_loss, take_profit, resolved, outcome, created_at, "
                "expires_at, created_ts) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    post_id,
                    user_id,
                    POST_KIND_DISCUSSION,
                    title,
                    body or None,
                    topic,  # may be '' — discussions don't require a market
                    "",     # direction unused for discussions
                    0.0, 0.0, 0.0,  # placeholder levels; never shown for discussions
                    0,
                    None,
                    _iso(now),
                    # Discussions don't expire on a trade TTL — give them a long life.
                    _iso(now + 365 * 24 * 3600),
                    int(now),
                ),
            )
        return self.get_post(post_id, viewer_id=user_id)

    def get_post(self, post_id: str, viewer_id: Optional[str] = None) -> dict:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
            if row is None:
                raise SocialError("post not found")
            return self._hydrate_post(conn, row, viewer_id)

    def list_posts(self, viewer_id: Optional[str] = None, limit: int = 50) -> List[dict]:
        limit = max(1, min(int(limit), 200))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM posts ORDER BY created_ts DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall()
            return [self._hydrate_post(conn, row, viewer_id) for row in rows]

    def list_feed_ranked(self, viewer_id: Optional[str] = None, limit: int = 50) -> List[dict]:
        """The proof-ranked FYP feed: recent posts re-ordered so the most
        credible, fresh, well-argued and well-voted calls rise to the top.

        Each returned post carries a ``rank_score`` and the author's
        ``track_record`` badge. New/anonymous visitors should land here."""
        limit = max(1, min(int(limit), 200))
        # Pull a wider candidate window than the page size so ranking can reach
        # past the few newest posts, then trim to the requested limit.
        candidate_window = max(limit * 4, 100)
        now = time.time()
        with closing(self._connect()) as conn:
            # The feed is for live, actionable content: open calls + discussions.
            # Resolved calls leave the feed — their proof lives on the author's
            # track-record badge, not by crowding the timeline.
            rows = conn.execute(
                "SELECT * FROM posts WHERE resolved = 0 "
                "ORDER BY created_ts DESC, rowid DESC LIMIT ?",
                (candidate_window,),
            ).fetchall()
            posts = [self._hydrate_post(conn, row, viewer_id) for row in rows]
            ages = {row["id"]: (now - int(row["created_ts"])) / 3600.0 for row in rows}
        for post in posts:
            record = post.get("track_record") or {}
            stats = post.get("prediction_stats") or {}
            # A call's substance is its reasoning; a discussion's is its body.
            substance = post.get("reasoning") if post.get("kind") != POST_KIND_DISCUSSION else post.get("body")
            post["rank_score"] = round(
                _rank_score(
                    credibility=record.get("credibility", 1.0),
                    age_hours=ages.get(post["id"], 0.0),
                    vote_score=post.get("score", 0),
                    has_thesis=bool(substance) and len(substance) >= RANK_THESIS_MIN_LEN,
                    crowd_calls=stats.get("tp_predictions", 0) + stats.get("sl_predictions", 0),
                    outcome=post.get("outcome"),
                ),
                6,
            )
        posts.sort(key=lambda p: p["rank_score"], reverse=True)
        return posts[:limit]

    def predict(self, user_id: str, post_id: str, outcome: str) -> dict:
        self._require_user(user_id)
        outcome = str(outcome).strip().lower()
        if outcome not in VALID_OUTCOMES:
            raise SocialError("predicted_outcome must be 'tp_hit' or 'sl_hit'")
        now = time.time()
        with closing(self._connect()) as conn, conn:
            post = conn.execute("SELECT kind FROM posts WHERE id = ?", (post_id,)).fetchone()
            if post is None:
                raise SocialError("post not found")
            if post["kind"] == POST_KIND_DISCUSSION:
                raise SocialError("discussions can't be predicted — they have no levels")
            existing = conn.execute(
                "SELECT id FROM predictions WHERE post_id = ? AND user_id = ?",
                (post_id, user_id),
            ).fetchone()
            if existing is not None:
                raise SocialError("you already called this setup")
            conn.execute(
                "INSERT INTO predictions(id, post_id, user_id, outcome, created_at) "
                "VALUES(?,?,?,?,?)",
                (_new_id(), post_id, user_id, outcome, _iso(now)),
            )
            conn.execute(
                "UPDATE users SET total_predictions = total_predictions + 1 WHERE id = ?",
                (user_id,),
            )
        return {"message": "prediction recorded"}

    def resolve_post(self, post_id: str, outcome: str) -> dict:
        """Close a call against its real outcome. This is what feeds the proof
        engine: it stamps the post's outcome and credits every crowd predictor
        who called it right (driving their ``correct_predictions``)."""
        outcome = str(outcome).strip().lower()
        if outcome not in VALID_OUTCOMES:
            raise SocialError("outcome must be 'tp_hit' or 'sl_hit'")
        with closing(self._connect()) as conn, conn:
            post = conn.execute(
                "SELECT resolved, kind FROM posts WHERE id = ?", (post_id,)
            ).fetchone()
            if post is None:
                raise SocialError("post not found")
            if post["kind"] == POST_KIND_DISCUSSION:
                raise SocialError("discussions don't resolve")
            if int(post["resolved"]):
                raise SocialError("post already resolved")
            conn.execute(
                "UPDATE posts SET resolved = 1, outcome = ? WHERE id = ?",
                (outcome, post_id),
            )
            # Credit everyone who predicted this outcome correctly.
            conn.execute(
                "UPDATE users SET correct_predictions = correct_predictions + 1 "
                "WHERE id IN (SELECT user_id FROM predictions "
                "WHERE post_id = ? AND outcome = ?)",
                (post_id, outcome),
            )
        return self.get_post(post_id)

    def expire_post(self, post_id: str) -> None:
        """Close a call as 'expired' (TTL elapsed without hitting a level).
        No predictor is credited — nobody was proven right or wrong."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE posts SET resolved = 1, outcome = 'expired' "
                "WHERE id = ? AND resolved = 0",
                (post_id,),
            )

    def resolve_open_posts(self, price_lookup, now: Optional[float] = None) -> dict:
        """Sweep every open call and close the ones the market has decided.

        ``price_lookup`` is a ``symbol -> Optional[float]`` callable, so this
        stays independent of any one price feed. A call whose price has crossed
        its target/stop is resolved (crediting correct predictors); a call past
        its TTL with no decision is expired. Returns a summary of what closed."""
        now = time.time() if now is None else now
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, symbol, direction, stop_loss, take_profit, expires_at "
                "FROM posts WHERE resolved = 0 AND kind = 'call'"
            ).fetchall()
        resolved: List[dict] = []
        expired: List[str] = []
        for row in rows:
            price = None
            try:
                price = price_lookup(row["symbol"])
            except Exception:  # a flaky feed must not abort the whole sweep
                price = None
            outcome = (
                _evaluate_outcome(row["direction"], price, row["stop_loss"], row["take_profit"])
                if price is not None
                else None
            )
            if outcome:
                self.resolve_post(row["id"], outcome)
                resolved.append({"post_id": row["id"], "outcome": outcome})
            elif _iso_to_ts(row["expires_at"]) <= now:
                self.expire_post(row["id"])
                expired.append(row["id"])
        return {
            "checked": len(rows),
            "resolved": resolved,
            "expired": expired,
        }

    def vote(self, user_id: str, post_id: str, direction: str) -> dict:
        """Boost (+1), Fade (-1), or clear a vote on a post. The post author's
        Reputation moves by the net change. Returns the post's new score and the
        caller's current vote."""
        self._require_user(user_id)
        direction = str(direction).strip().lower()
        if direction not in VOTE_VALUES and direction != "clear":
            raise SocialError("direction must be 'boost', 'fade', or 'clear'")
        new_value = VOTE_VALUES.get(direction, 0)
        now = time.time()
        with closing(self._connect()) as conn, conn:
            post = conn.execute(
                "SELECT author_id FROM posts WHERE id = ?", (post_id,)
            ).fetchone()
            if post is None:
                raise SocialError("post not found")
            author_id = post["author_id"]
            prior = conn.execute(
                "SELECT value FROM votes WHERE post_id = ? AND user_id = ?",
                (post_id, user_id),
            ).fetchone()
            old_value = int(prior["value"]) if prior is not None else 0

            if new_value == 0:
                conn.execute(
                    "DELETE FROM votes WHERE post_id = ? AND user_id = ?",
                    (post_id, user_id),
                )
            elif prior is None:
                conn.execute(
                    "INSERT INTO votes(id, post_id, user_id, value, created_at) VALUES(?,?,?,?,?)",
                    (_new_id(), post_id, user_id, new_value, _iso(now)),
                )
            else:
                conn.execute(
                    "UPDATE votes SET value = ?, created_at = ? WHERE post_id = ? AND user_id = ?",
                    (new_value, _iso(now), post_id, user_id),
                )

            delta = new_value - old_value
            if delta:
                conn.execute(
                    "UPDATE users SET reputation = reputation + ? WHERE id = ?",
                    (delta, author_id),
                )
            score = conn.execute(
                "SELECT COALESCE(SUM(value), 0) AS score FROM votes WHERE post_id = ?",
                (post_id,),
            ).fetchone()["score"]
        viewer_vote = next((k for k, v in VOTE_VALUES.items() if v == new_value), None)
        return {"post_id": post_id, "score": int(score), "viewer_vote": viewer_vote}

    # --------------------------------------------------------------- comments
    def list_comments(self, post_id: str, viewer_id: Optional[str] = None, limit: int = 100) -> List[dict]:
        limit = max(1, min(int(limit), 500))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT c.*, u.id AS u_id, u.username, u.gold, u.total_predictions, "
                "u.correct_predictions, u.trust_level, u.reputation, u.created_at AS u_created_at, "
                "COALESCE((SELECT SUM(value) FROM comment_votes cv WHERE cv.comment_id = c.id), 0) AS score "
                "FROM comments c JOIN users u ON u.id = c.user_id "
                # Community voice rises: best-voted replies first, then oldest.
                "WHERE c.post_id = ? ORDER BY score DESC, c.created_ts ASC, c.rowid ASC LIMIT ?",
                (post_id, limit),
            ).fetchall()
            return [self._comment_with_viewer(conn, row, viewer_id) for row in rows]

    def vote_comment(self, user_id: str, comment_id: str, direction: str) -> dict:
        """Boost/Fade/clear a vote on a comment — so the community's best takes
        rise. Returns the comment's new score and the caller's current vote."""
        self._require_user(user_id)
        direction = str(direction).strip().lower()
        if direction not in VOTE_VALUES and direction != "clear":
            raise SocialError("direction must be 'boost', 'fade', or 'clear'")
        new_value = VOTE_VALUES.get(direction, 0)
        now = time.time()
        with closing(self._connect()) as conn, conn:
            comment = conn.execute(
                "SELECT user_id FROM comments WHERE id = ?", (comment_id,)
            ).fetchone()
            if comment is None:
                raise SocialError("comment not found")
            prior = conn.execute(
                "SELECT value FROM comment_votes WHERE comment_id = ? AND user_id = ?",
                (comment_id, user_id),
            ).fetchone()
            old_value = int(prior["value"]) if prior is not None else 0
            if new_value == 0:
                conn.execute(
                    "DELETE FROM comment_votes WHERE comment_id = ? AND user_id = ?",
                    (comment_id, user_id),
                )
            elif prior is None:
                conn.execute(
                    "INSERT INTO comment_votes(id, comment_id, user_id, value, created_at) "
                    "VALUES(?,?,?,?,?)",
                    (_new_id(), comment_id, user_id, new_value, _iso(now)),
                )
            else:
                conn.execute(
                    "UPDATE comment_votes SET value = ?, created_at = ? "
                    "WHERE comment_id = ? AND user_id = ?",
                    (new_value, _iso(now), comment_id, user_id),
                )
            # The comment author's reputation moves with their take's reception.
            delta = new_value - old_value
            if delta:
                conn.execute(
                    "UPDATE users SET reputation = reputation + ? WHERE id = ?",
                    (delta, comment["user_id"]),
                )
            score = conn.execute(
                "SELECT COALESCE(SUM(value), 0) AS score FROM comment_votes WHERE comment_id = ?",
                (comment_id,),
            ).fetchone()["score"]
        viewer_vote = next((k for k, v in VOTE_VALUES.items() if v == new_value), None)
        return {"comment_id": comment_id, "score": int(score), "viewer_vote": viewer_vote}

    def _comment_with_viewer(self, conn, row, viewer_id: Optional[str]) -> dict:
        data = _comment_dict(row)
        data["score"] = int(row["score"]) if "score" in row.keys() else 0
        data["viewer_vote"] = None
        if viewer_id:
            mine = conn.execute(
                "SELECT value FROM comment_votes WHERE comment_id = ? AND user_id = ?",
                (row["id"], viewer_id),
            ).fetchone()
            if mine is not None:
                data["viewer_vote"] = next(
                    (k for k, v in VOTE_VALUES.items() if v == int(mine["value"])), None
                )
        return data

    def add_comment(self, user_id: str, post_id: str, content: str) -> dict:
        self._require_user(user_id)
        text = str(content or "").strip()
        if not text:
            raise SocialError("comment content is required")
        if len(text) > 2000:
            raise SocialError("comment is too long")
        now = time.time()
        comment_id = _new_id()
        with closing(self._connect()) as conn, conn:
            post = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
            if post is None:
                raise SocialError("post not found")
            conn.execute(
                "INSERT INTO comments(id, post_id, user_id, content, created_at, created_ts) "
                "VALUES(?,?,?,?,?,?)",
                (comment_id, post_id, user_id, text, _iso(now), int(now)),
            )
            row = conn.execute(
                "SELECT c.*, u.id AS u_id, u.username, u.gold, u.total_predictions, "
                "u.correct_predictions, u.trust_level, u.reputation, u.created_at AS u_created_at "
                "FROM comments c JOIN users u ON u.id = c.user_id WHERE c.id = ?",
                (comment_id,),
            ).fetchone()
        return _comment_dict(row)

    # ---------------------------------------------------------------- helpers
    def _require_user(self, user_id: str) -> None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise SocialError("user not found")

    # ------------------------------------------------------------ reputation
    def author_track_record(self, user_id: str) -> dict:
        """Public, audited proof badge for an author: their resolved-call win
        rate, crowd-prediction accuracy, reputation and Gold, plus the single
        ``credibility`` multiplier the feed ranks on. This is what makes the
        feed *proof*-ranked rather than popularity-ranked."""
        with closing(self._connect()) as conn:
            record = self._author_track_record(conn, user_id)
        if record is None:
            raise SocialError("user not found")
        return record

    def _author_track_record(self, conn: sqlite3.Connection, user_id: str) -> Optional[dict]:
        user = conn.execute(
            "SELECT total_predictions, correct_predictions, reputation, gold "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            return None
        calls = conn.execute(
            "SELECT COUNT(*) AS n, "
            "COALESCE(SUM(CASE WHEN outcome = 'tp_hit' THEN 1 ELSE 0 END), 0) AS wins "
            "FROM posts WHERE author_id = ? AND resolved = 1",
            (user_id,),
        ).fetchone()
        resolved_calls = int(calls["n"])
        winning_calls = int(calls["wins"])
        smoothed = (winning_calls + RANK_PRIOR_CALLS * RANK_PRIOR_WINRATE) / (
            resolved_calls + RANK_PRIOR_CALLS
        )
        total_p = int(user["total_predictions"])
        correct_p = int(user["correct_predictions"])
        call_win_rate = (winning_calls / resolved_calls) if resolved_calls else None
        prediction_accuracy = (correct_p / total_p) if total_p else None
        credibility = _credibility(smoothed, int(user["reputation"]), int(user["gold"]))
        return {
            "resolved_calls": resolved_calls,
            "winning_calls": winning_calls,
            "call_win_rate": round(call_win_rate, 4) if call_win_rate is not None else None,
            "prediction_accuracy": round(prediction_accuracy, 4)
            if prediction_accuracy is not None
            else None,
            "reputation": int(user["reputation"]),
            "gold": int(user["gold"]),
            "credibility": round(credibility, 4),
        }

    def _hydrate_post(self, conn: sqlite3.Connection, row: sqlite3.Row, viewer_id: Optional[str]) -> dict:
        author = conn.execute("SELECT * FROM users WHERE id = ?", (row["author_id"],)).fetchone()
        tp = conn.execute(
            "SELECT COUNT(*) AS n FROM predictions WHERE post_id = ? AND outcome = 'tp_hit'",
            (row["id"],),
        ).fetchone()["n"]
        sl = conn.execute(
            "SELECT COUNT(*) AS n FROM predictions WHERE post_id = ? AND outcome = 'sl_hit'",
            (row["id"],),
        ).fetchone()["n"]
        user_prediction = None
        viewer_vote = None
        if viewer_id:
            mine = conn.execute(
                "SELECT outcome FROM predictions WHERE post_id = ? AND user_id = ?",
                (row["id"], viewer_id),
            ).fetchone()
            if mine is not None:
                user_prediction = mine["outcome"]
            my_vote = conn.execute(
                "SELECT value FROM votes WHERE post_id = ? AND user_id = ?",
                (row["id"], viewer_id),
            ).fetchone()
            if my_vote is not None:
                viewer_vote = next((k for k, v in VOTE_VALUES.items() if v == int(my_vote["value"])), None)
        score = conn.execute(
            "SELECT COALESCE(SUM(value), 0) AS score FROM votes WHERE post_id = ?",
            (row["id"],),
        ).fetchone()["score"]
        track_record = self._author_track_record(conn, row["author_id"])
        # The top community take, surfaced on the card so you see what people are
        # saying without opening the thread. Best-voted wins; ties break oldest.
        top = conn.execute(
            "SELECT c.content, u.username, "
            "COALESCE((SELECT SUM(value) FROM comment_votes cv WHERE cv.comment_id = c.id), 0) AS score "
            "FROM comments c JOIN users u ON u.id = c.user_id "
            "WHERE c.post_id = ? ORDER BY score DESC, c.created_ts ASC, c.rowid ASC LIMIT 1",
            (row["id"],),
        ).fetchone()
        comment_count = conn.execute(
            "SELECT COUNT(*) AS n FROM comments WHERE post_id = ?", (row["id"],)
        ).fetchone()["n"]
        top_comment = (
            {"username": top["username"], "content": top["content"], "score": int(top["score"])}
            if top is not None
            else None
        )
        keys = row.keys()
        kind = row["kind"] if "kind" in keys else POST_KIND_CALL
        return {
            "id": row["id"],
            "kind": kind,
            "title": row["title"] if "title" in keys else None,
            "body": row["body"] if "body" in keys else None,
            "user": _user_dict(author),
            "track_record": track_record,
            "symbol": row["symbol"],
            "direction": row["direction"],
            "entry_price": row["entry_price"],
            "stop_loss": row["stop_loss"],
            "take_profit": row["take_profit"],
            "reasoning": row["reasoning"],
            "chart_image_url": row["chart_image_url"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "resolved": bool(row["resolved"]),
            "outcome": row["outcome"],
            "foxtrot_score": row["foxtrot_score"],
            "regime": row["regime"],
            "confidence": row["confidence"],
            "prediction_stats": {"tp_predictions": tp, "sl_predictions": sl},
            "user_prediction": user_prediction,
            "score": int(score),
            "viewer_vote": viewer_vote,
            "comment_count": int(comment_count),
            "top_comment": top_comment,
        }


def _user_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "gold": row["gold"],
        "total_predictions": row["total_predictions"],
        "correct_predictions": row["correct_predictions"],
        "trust_level": row["trust_level"],
        "reputation": row["reputation"],
        "created_at": row["created_at"],
    }


def _comment_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "user": {
            "id": row["u_id"],
            "username": row["username"],
            "gold": row["gold"],
            "total_predictions": row["total_predictions"],
            "correct_predictions": row["correct_predictions"],
            "trust_level": row["trust_level"],
            "reputation": row["reputation"],
            "created_at": row["u_created_at"],
        },
        "content": row["content"],
        "created_at": row["created_at"],
    }


def _normalize_username(username: str) -> str:
    handle = str(username or "").strip()
    if handle.startswith("@"):
        handle = handle[1:]
    if not handle:
        raise SocialError("username is required")
    if len(handle) > 40:
        raise SocialError("username is too long")
    return handle


def _positive_number(value, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SocialError(f"{field} must be a number") from exc
    if not number > 0:
        raise SocialError(f"{field} must be positive")
    return number


def _optional_number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_optional_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _default_db_path() -> Path:
    override = os.environ.get("COINFOX_SOCIAL_DB")
    if override:
        return Path(override)
    return Path.home() / ".coinfox" / "social.sqlite"
