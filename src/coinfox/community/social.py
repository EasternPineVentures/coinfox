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
"""

# Boost = upvote (+1), Fade = downvote (-1). "clear" removes an existing vote.
VOTE_VALUES = {"boost": 1, "fade": -1}


def _iso(ts: Optional[float] = None) -> str:
    moment = datetime.fromtimestamp(ts, tz=timezone.utc) if ts is not None else datetime.now(timezone.utc)
    return moment.isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return uuid.uuid4().hex


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
                "INSERT INTO posts(id, author_id, symbol, direction, entry_price, "
                "stop_loss, take_profit, reasoning, chart_image_url, foxtrot_score, "
                "regime, confidence, resolved, outcome, created_at, expires_at, created_ts) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    post_id,
                    user_id,
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

    def predict(self, user_id: str, post_id: str, outcome: str) -> dict:
        self._require_user(user_id)
        outcome = str(outcome).strip().lower()
        if outcome not in VALID_OUTCOMES:
            raise SocialError("predicted_outcome must be 'tp_hit' or 'sl_hit'")
        now = time.time()
        with closing(self._connect()) as conn, conn:
            post = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
            if post is None:
                raise SocialError("post not found")
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
    def list_comments(self, post_id: str, limit: int = 100) -> List[dict]:
        limit = max(1, min(int(limit), 500))
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT c.*, u.id AS u_id, u.username, u.gold, u.total_predictions, "
                "u.correct_predictions, u.trust_level, u.reputation, u.created_at AS u_created_at "
                "FROM comments c JOIN users u ON u.id = c.user_id "
                "WHERE c.post_id = ? ORDER BY c.created_ts ASC, c.rowid ASC LIMIT ?",
                (post_id, limit),
            ).fetchall()
        return [_comment_dict(row) for row in rows]

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
        return {
            "id": row["id"],
            "user": _user_dict(author),
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
