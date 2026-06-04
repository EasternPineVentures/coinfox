"""Local community arena for the NY Fox Exchange (bragging-rights Gold economy).

Currency: Gold (g).  1 unit = 1 gram of gold, for fun only.
  - Every user starts with STARTING_BALANCE_FC grams.
  - If you hit 0, you may borrow up to LOAN_MAX_GOLD at LOAN_INTEREST_RATE interest.
  - Only one open loan at a time; a second borrow is blocked while debt is outstanding.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import List, Optional

from .market_hours import (
    NYFE_TIMEZONE,
    NYFE_OPEN_HOUR,
    NYFE_OPEN_MINUTE,
    NYFE_CLOSE_HOUR,
    NYFE_CLOSE_MINUTE,
    _market_session,
    format_market_timestamp,
    market_now_text,
    nyfe_timestamp,
)
from .models import (
    ArenaError,
    Bet,
    Comment,
    FeedEvent,
    Idea,
    Loan,
    MarketSession,
    NotEnoughGold,
    NotEnoughFoxcoin,
    Position,
    PositionMark,
    Post,
    Profile,
    UserAccount,
    UserStats,
)


# ---------------------------------------------------------------------------
# Economy constants
# ---------------------------------------------------------------------------
STARTING_BALANCE_FC = 500          # Gold grams every new user starts with
LOAN_MAX_GOLD = 1000               # Maximum a user may borrow in one loan
LOAN_INTEREST_RATE = 0.20          # 20 % interest charged on principal at repayment
BANKRUPTCY_RESCUE_FC = 100        # kept for backward-compat imports only
BANKRUPTCY_RESCUE_COOLDOWN_S = 30 * 24 * 60 * 60  # legacy; not used by loan system
VALID_DIRECTIONS = {"long", "short", "neutral"}
TRADABLE_DIRECTIONS = {"long", "short"}


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    handle      TEXT PRIMARY KEY,
    created_ts  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    handle        TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL,
    bio           TEXT NOT NULL DEFAULT '',
    created_ts    INTEGER NOT NULL,
    updated_ts    INTEGER NOT NULL,
    FOREIGN KEY(handle) REFERENCES users(handle)
);
CREATE INDEX IF NOT EXISTS idx_profiles_updated
    ON profiles(updated_ts DESC);
CREATE TABLE IF NOT EXISTS wallet_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    handle      TEXT NOT NULL,
    delta_fc    INTEGER NOT NULL,
    reason      TEXT NOT NULL,
    ref_kind    TEXT,
    ref_id      INTEGER,
    created_ts  INTEGER NOT NULL,
    FOREIGN KEY(handle) REFERENCES users(handle)
);
CREATE INDEX IF NOT EXISTS idx_wallet_ledger_handle_ts
    ON wallet_ledger(handle, created_ts DESC);
CREATE TABLE IF NOT EXISTS ideas (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    author_handle    TEXT NOT NULL,
    title            TEXT NOT NULL,
    body             TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    bias             TEXT NOT NULL,
    status           TEXT NOT NULL,
    resolution_rule  TEXT NOT NULL,
    closes_ts        INTEGER,
    created_ts       INTEGER NOT NULL,
    resolved_ts      INTEGER,
    outcome          TEXT,
    resolver_handle  TEXT
);
CREATE INDEX IF NOT EXISTS idx_ideas_status_created
    ON ideas(status, created_ts DESC);
CREATE TABLE IF NOT EXISTS comments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id        INTEGER NOT NULL,
    author_handle  TEXT NOT NULL,
    body           TEXT NOT NULL,
    created_ts     INTEGER NOT NULL,
    FOREIGN KEY(idea_id) REFERENCES ideas(id)
);
CREATE INDEX IF NOT EXISTS idx_comments_idea_ts
    ON comments(idea_id, created_ts ASC);
CREATE TABLE IF NOT EXISTS bets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id      INTEGER NOT NULL,
    handle       TEXT NOT NULL,
    direction    TEXT NOT NULL,
    amount_fc    INTEGER NOT NULL,
    payout_fc    INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL,
    placed_ts    INTEGER NOT NULL,
    settled_ts   INTEGER,
    FOREIGN KEY(idea_id) REFERENCES ideas(id),
    FOREIGN KEY(handle) REFERENCES users(handle)
);
CREATE INDEX IF NOT EXISTS idx_bets_idea_ts
    ON bets(idea_id, placed_ts ASC);
CREATE TABLE IF NOT EXISTS positions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    handle           TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    direction        TEXT NOT NULL,
    amount_fc        INTEGER NOT NULL,
    entry_price      REAL NOT NULL,
    exit_price       REAL,
    status           TEXT NOT NULL,
    realized_pnl_fc  INTEGER NOT NULL DEFAULT 0,
    opened_ts        INTEGER NOT NULL,
    closed_ts        INTEGER,
    FOREIGN KEY(handle) REFERENCES users(handle)
);
CREATE INDEX IF NOT EXISTS idx_positions_handle_status_opened
    ON positions(handle, status, opened_ts DESC);
CREATE TABLE IF NOT EXISTS posts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    author_handle  TEXT NOT NULL,
    body           TEXT NOT NULL,
    created_ts     INTEGER NOT NULL,
    FOREIGN KEY(author_handle) REFERENCES users(handle)
);
CREATE INDEX IF NOT EXISTS idx_posts_author_created
    ON posts(author_handle, created_ts DESC);
CREATE TABLE IF NOT EXISTS loans (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    handle         TEXT NOT NULL,
    principal_fc   INTEGER NOT NULL,
    interest_fc    INTEGER NOT NULL,
    status         TEXT NOT NULL DEFAULT 'open',
    borrowed_ts    INTEGER NOT NULL,
    repaid_ts      INTEGER,
    FOREIGN KEY(handle) REFERENCES users(handle)
);
CREATE INDEX IF NOT EXISTS idx_loans_handle_status
    ON loans(handle, status, borrowed_ts DESC);
CREATE TABLE IF NOT EXISTS feed_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    handle        TEXT,
    event_type    TEXT NOT NULL,
    ref_kind      TEXT,
    ref_id        INTEGER,
    headline      TEXT NOT NULL,
    body          TEXT NOT NULL,
    created_ts    INTEGER NOT NULL,
    FOREIGN KEY(handle) REFERENCES users(handle)
);
CREATE INDEX IF NOT EXISTS idx_feed_events_created
    ON feed_events(created_ts DESC, id DESC);
"""


class Arena:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        identity_path: Optional[Path] = None,
        price_fetcher=None,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.identity_path = Path(identity_path) if identity_path is not None else _default_identity_path()
        self._price_fetcher = price_fetcher
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.identity_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)

    def ensure_user(self, handle: str) -> UserAccount:
        normalized = _normalize_handle(handle)
        now = int(time.time())
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT handle, created_ts FROM users WHERE handle = ?",
                (normalized,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO users(handle, created_ts) VALUES(?, ?)",
                    (normalized, now),
                )
                self._record_ledger(conn, normalized, STARTING_BALANCE_FC, "starting_grant", created_ts=now)
                created_ts = now
            else:
                created_ts = int(row["created_ts"])
            self._ensure_profile_row(conn, normalized, created_ts, now)
        return UserAccount(handle=normalized, balance_fc=self.balance(normalized), created_ts=created_ts)

    def get_user(self, handle: str) -> Optional[UserAccount]:
        normalized = _normalize_handle(handle)
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT handle, created_ts FROM users WHERE handle = ?",
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        return UserAccount(
            handle=str(row["handle"]),
            balance_fc=self.balance(normalized),
            created_ts=int(row["created_ts"]),
        )

    def balance(self, handle: str) -> int:
        normalized = _normalize_handle(handle)
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(delta_fc), 0) AS balance_fc FROM wallet_ledger WHERE handle = ?",
                (normalized,),
            ).fetchone()
        return int(row["balance_fc"] if row is not None else 0)

    def set_identity(self, handle: str) -> UserAccount:
        user = self.ensure_user(handle)
        self.identity_path.write_text(user.handle, encoding="utf-8")
        return user

    def get_profile(self, handle: str) -> Profile:
        user = self.ensure_user(handle)
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM profiles WHERE handle = ?", (user.handle,)).fetchone()
        if row is None:
            raise ArenaError(f"profile for {user.handle} does not exist")
        return _profile_from_row(row)

    def update_profile(self, handle: str, display_name: Optional[str] = None, bio: Optional[str] = None) -> Profile:
        user = self.ensure_user(handle)
        current = self.get_profile(user.handle)
        next_display_name = (display_name or current.display_name).strip()
        next_bio = (bio if bio is not None else current.bio).strip()
        if not next_display_name:
            raise ArenaError("display name is required")
        now = int(time.time())
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE profiles SET display_name = ?, bio = ?, updated_ts = ? WHERE handle = ?",
                (next_display_name, next_bio, now, user.handle),
            )
        return self.get_profile(user.handle)

    def create_post(self, handle: str, body: str) -> Post:
        user = self.ensure_user(handle)
        text = body.strip()
        if not text:
            raise ArenaError("post body is required")
        now = int(time.time())
        profile = self.get_profile(user.handle)
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO posts(author_handle, body, created_ts) VALUES(?, ?, ?)",
                (user.handle, text, now),
            )
            post_id = int(cur.lastrowid)
            self._emit_feed_event(
                conn,
                user.handle,
                "post",
                f"{profile.display_name} posted an update",
                text,
                ref_kind="post",
                ref_id=post_id,
                created_ts=now,
            )
        return self.get_post(post_id)

    def get_post(self, post_id: int) -> Post:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM posts WHERE id = ?", (int(post_id),)).fetchone()
        if row is None:
            raise ArenaError(f"post {post_id} does not exist")
        return _post_from_row(row)

    def list_posts(self, handle: Optional[str] = None, limit: int = 20) -> List[Post]:
        if handle is not None:
            normalized = _normalize_handle(handle)
            query = "SELECT * FROM posts WHERE author_handle = ? ORDER BY created_ts DESC, id DESC LIMIT ?"
            params = (normalized, max(1, int(limit)))
        else:
            query = "SELECT * FROM posts ORDER BY created_ts DESC, id DESC LIMIT ?"
            params = (max(1, int(limit)),)
        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [_post_from_row(row) for row in rows]

    def feed(self, limit: int = 20, handle: Optional[str] = None) -> List[FeedEvent]:
        if handle is not None:
            normalized = _normalize_handle(handle)
            query = "SELECT * FROM feed_events WHERE handle = ? ORDER BY created_ts DESC, id DESC LIMIT ?"
            params = (normalized, max(1, int(limit)))
        else:
            query = "SELECT * FROM feed_events ORDER BY created_ts DESC, id DESC LIMIT ?"
            params = (max(1, int(limit)),)
        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [_feed_event_from_row(row) for row in rows]

    def identity(self) -> Optional[str]:
        if not self.identity_path.exists():
            return None
        raw = self.identity_path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        return _normalize_handle(raw)

    def create_idea(
        self,
        author_handle: str,
        title: str,
        body: str,
        symbol: str,
        bias: str,
        resolution_rule: str,
        closes_ts: Optional[int] = None,
    ) -> Idea:
        title = title.strip()
        body = body.strip()
        symbol = symbol.strip().upper() or "BTCUSDT"
        resolution_rule = resolution_rule.strip()
        direction = _normalize_direction(bias)
        if not title:
            raise ArenaError("idea title is required")
        if not body:
            raise ArenaError("idea body is required")
        if not resolution_rule:
            raise ArenaError("resolution rule is required")
        author = self.ensure_user(author_handle).handle
        profile = self.get_profile(author)
        now = int(time.time())
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                """
                INSERT INTO ideas(
                    author_handle, title, body, symbol, bias, status,
                    resolution_rule, closes_ts, created_ts
                ) VALUES(?, ?, ?, ?, ?, 'open', ?, ?, ?)
                """,
                (author, title, body, symbol, direction, resolution_rule, closes_ts, now),
            )
            idea_id = int(cur.lastrowid)
            self._emit_feed_event(
                conn,
                author,
                "idea",
                f"{profile.display_name} posted a {direction.upper()} idea on {symbol}",
                title,
                ref_kind="idea",
                ref_id=idea_id,
                created_ts=now,
            )
        idea = self.get_idea(idea_id)
        assert idea is not None
        return idea

    def list_ideas(self, status: Optional[str] = "open", limit: int = 20) -> List[Idea]:
        query = (
            "SELECT * FROM ideas WHERE status = ? ORDER BY created_ts DESC LIMIT ?"
            if status
            else "SELECT * FROM ideas ORDER BY created_ts DESC LIMIT ?"
        )
        params = (status, max(1, int(limit))) if status else (max(1, int(limit)),)
        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [_idea_from_row(row) for row in rows]

    def get_idea(self, idea_id: int) -> Optional[Idea]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM ideas WHERE id = ?", (int(idea_id),)).fetchone()
        return _idea_from_row(row) if row else None

    def add_comment(self, idea_id: int, author_handle: str, body: str) -> Comment:
        idea = self.get_idea(idea_id)
        if idea is None:
            raise ArenaError(f"idea {idea_id} does not exist")
        message = body.strip()
        if not message:
            raise ArenaError("comment body is required")
        author = self.ensure_user(author_handle).handle
        profile = self.get_profile(author)
        now = int(time.time())
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO comments(idea_id, author_handle, body, created_ts) VALUES(?, ?, ?, ?)",
                (int(idea_id), author, message, now),
            )
            comment_id = int(cur.lastrowid)
            self._emit_feed_event(
                conn,
                author,
                "comment",
                f"{profile.display_name} commented on idea #{idea_id}",
                message,
                ref_kind="comment",
                ref_id=comment_id,
                created_ts=now,
            )
        return Comment(comment_id, int(idea_id), author, message, now)

    def comments(self, idea_id: int, limit: int = 50) -> List[Comment]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM comments WHERE idea_id = ? ORDER BY created_ts ASC LIMIT ?",
                (int(idea_id), max(1, int(limit))),
            ).fetchall()
        return [
            Comment(
                id=int(row["id"]),
                idea_id=int(row["idea_id"]),
                author_handle=str(row["author_handle"]),
                body=str(row["body"]),
                created_ts=int(row["created_ts"]),
            )
            for row in rows
        ]

    def place_bet(
        self,
        idea_id: int,
        handle: str,
        direction: str,
        amount_fc: int,
        now_ts: Optional[int] = None,
    ) -> Bet:
        idea = self.get_idea(idea_id)
        if idea is None:
            raise ArenaError(f"idea {idea_id} does not exist")
        if idea.status != "open":
            raise ArenaError("betting is closed for this idea")
        now = int(now_ts if now_ts is not None else time.time())
        self._require_market_open(now)
        if idea.closes_ts is not None and now >= int(idea.closes_ts):
            raise ArenaError("this idea has already reached its closing time")
        amount = int(amount_fc)
        if amount <= 0:
            raise ArenaError("bet amount must be positive")
        user = self.ensure_user(handle)
        wager_direction = _normalize_direction(direction)
        if user.balance_fc < amount:
            raise NotEnoughFoxcoin(f"{user.handle} only has {user.balance_fc} FC")

        with closing(self._connect()) as conn, conn:
            self._record_ledger(
                conn,
                user.handle,
                -amount,
                "bet_escrow",
                ref_kind="idea",
                ref_id=int(idea_id),
                created_ts=now,
            )
            cur = conn.execute(
                """
                INSERT INTO bets(idea_id, handle, direction, amount_fc, status, placed_ts)
                VALUES(?, ?, ?, ?, 'open', ?)
                """,
                (int(idea_id), user.handle, wager_direction, amount, now),
            )
            bet_id = int(cur.lastrowid)
        return self.get_bet(bet_id)

    def market_session(self, now_ts: Optional[int] = None) -> MarketSession:
        return _market_session(now_ts)

    def open_position(
        self,
        handle: str,
        symbol: str,
        direction: str,
        amount_fc: int,
        now_ts: Optional[int] = None,
        price: Optional[float] = None,
    ) -> Position:
        now = int(now_ts if now_ts is not None else time.time())
        self._require_market_open(now)
        side = _normalize_trade_direction(direction)
        amount = int(amount_fc)
        if amount <= 0:
            raise ArenaError("trade amount must be positive")
        user = self.ensure_user(handle)
        profile = self.get_profile(user.handle)
        if user.balance_fc < amount:
            raise NotEnoughFoxcoin(f"{user.handle} only has {user.balance_fc} FC")
        trade_symbol = symbol.strip().upper() or "BTCUSDT"
        entry_price = float(price if price is not None else self._price_for(trade_symbol))
        if entry_price <= 0:
            raise ArenaError("entry price must be positive")

        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                """
                INSERT INTO positions(handle, symbol, direction, amount_fc, entry_price, status, opened_ts)
                VALUES(?, ?, ?, ?, ?, 'open', ?)
                """,
                (user.handle, trade_symbol, side, amount, entry_price, now),
            )
            position_id = int(cur.lastrowid)
            self._record_ledger(
                conn,
                user.handle,
                -amount,
                "position_open",
                ref_kind="position",
                ref_id=position_id,
                created_ts=now,
            )
            self._emit_feed_event(
                conn,
                user.handle,
                "position_open",
                f"{profile.display_name} opened a {side.upper()} position on {trade_symbol}",
                f"Stake: {amount} FC at {entry_price:.2f}",
                ref_kind="position",
                ref_id=position_id,
                created_ts=now,
            )
        return self.get_position(position_id)

    def close_position(
        self,
        position_id: int,
        handle: str,
        now_ts: Optional[int] = None,
        price: Optional[float] = None,
    ) -> Position:
        now = int(now_ts if now_ts is not None else time.time())
        self._require_market_open(now)
        user = self.ensure_user(handle)
        profile = self.get_profile(user.handle)
        position = self.get_position(position_id)
        if position.handle != user.handle:
            raise ArenaError("you can only close your own positions")
        if position.status != "open":
            raise ArenaError("position is already closed")

        exit_price = float(price if price is not None else self._price_for(position.symbol))
        if exit_price <= 0:
            raise ArenaError("exit price must be positive")
        payout_fc, pnl_fc = _settle_position_amount(
            amount_fc=position.amount_fc,
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=exit_price,
        )
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE positions
                SET exit_price = ?, status = 'closed', realized_pnl_fc = ?, closed_ts = ?
                WHERE id = ?
                """,
                (exit_price, pnl_fc, now, int(position_id)),
            )
            self._record_ledger(
                conn,
                user.handle,
                payout_fc,
                "position_close",
                ref_kind="position",
                ref_id=int(position_id),
                created_ts=now,
            )
            pnl_text = f"+{pnl_fc}" if pnl_fc > 0 else str(pnl_fc)
            self._emit_feed_event(
                conn,
                user.handle,
                "position_close",
                f"{profile.display_name} closed a {position.direction.upper()} position on {position.symbol}",
                f"PnL: {pnl_text} FC at {exit_price:.2f}",
                ref_kind="position",
                ref_id=int(position_id),
                created_ts=now,
            )
        return self.get_position(position_id)

    def get_position(self, position_id: int) -> Position:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM positions WHERE id = ?", (int(position_id),)).fetchone()
        if row is None:
            raise ArenaError(f"position {position_id} does not exist")
        return _position_from_row(row)

    def positions(self, handle: Optional[str] = None, status: Optional[str] = None, limit: int = 20) -> List[Position]:
        clauses = []
        params = []
        if handle is not None:
            clauses.append("handle = ?")
            params.append(_normalize_handle(handle))
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, int(limit)))
        query = f"SELECT * FROM positions{where} ORDER BY opened_ts DESC, id DESC LIMIT ?"
        with closing(self._connect()) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [_position_from_row(row) for row in rows]

    def marked_positions(
        self,
        handle: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[PositionMark]:
        positions = self.positions(handle=handle, status=status, limit=limit)
        prices: dict[str, Optional[float]] = {}
        marks: List[PositionMark] = []
        for position in positions:
            if position.status == "closed":
                marks.append(
                    PositionMark(
                        position=position,
                        current_price=position.exit_price,
                        unrealized_pnl_fc=position.realized_pnl_fc,
                        gross_value_fc=position.amount_fc + position.realized_pnl_fc,
                    )
                )
                continue
            if position.symbol not in prices:
                try:
                    prices[position.symbol] = self._price_for(position.symbol)
                except Exception:
                    prices[position.symbol] = None
            current_price = prices[position.symbol]
            if current_price is None:
                marks.append(PositionMark(position=position, current_price=None, unrealized_pnl_fc=None, gross_value_fc=None))
                continue
            gross_value_fc, unrealized_pnl_fc = _settle_position_amount(
                amount_fc=position.amount_fc,
                direction=position.direction,
                entry_price=position.entry_price,
                exit_price=current_price,
            )
            marks.append(
                PositionMark(
                    position=position,
                    current_price=current_price,
                    unrealized_pnl_fc=unrealized_pnl_fc,
                    gross_value_fc=gross_value_fc,
                )
            )
        return marks

    def user_stats(self, handle: str) -> UserStats:
        normalized = _normalize_handle(handle)
        user = self.ensure_user(normalized)
        positions = self.positions(handle=normalized, status=None, limit=1000)
        marks = self.marked_positions(handle=normalized, status="open", limit=1000)
        closed_positions = [position for position in positions if position.status == "closed"]
        winning_positions = sum(1 for position in closed_positions if position.realized_pnl_fc > 0)
        losing_positions = sum(1 for position in closed_positions if position.realized_pnl_fc < 0)
        realized_pnl_fc = sum(position.realized_pnl_fc for position in closed_positions)
        unrealized_pnl_fc = sum(mark.unrealized_pnl_fc or 0 for mark in marks)
        total_staked_fc = sum(position.amount_fc for position in positions)
        return UserStats(
            handle=user.handle,
            balance_fc=user.balance_fc,
            open_positions=len(marks),
            closed_positions=len(closed_positions),
            winning_positions=winning_positions,
            losing_positions=losing_positions,
            realized_pnl_fc=realized_pnl_fc,
            unrealized_pnl_fc=unrealized_pnl_fc,
            total_staked_fc=total_staked_fc,
        )

    def stats_leaderboard(self, limit: int = 10) -> List[UserStats]:
        users = self.leaderboard(limit=max(1, int(limit * 5)))
        stats = [self.user_stats(user.handle) for user in users]
        stats.sort(
            key=lambda stat: (
                stat.realized_pnl_fc,
                stat.winning_positions,
                stat.balance_fc,
                -stat.losing_positions,
            ),
            reverse=True,
        )
        return stats[: max(1, int(limit))]

    def get_bet(self, bet_id: int) -> Bet:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM bets WHERE id = ?", (int(bet_id),)).fetchone()
        if row is None:
            raise ArenaError(f"bet {bet_id} does not exist")
        return _bet_from_row(row)

    def bets_for_idea(self, idea_id: int) -> List[Bet]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM bets WHERE idea_id = ? ORDER BY placed_ts ASC, id ASC",
                (int(idea_id),),
            ).fetchall()
        return [_bet_from_row(row) for row in rows]

    def resolve_idea(self, idea_id: int, outcome: str, resolver_handle: str) -> Idea:
        idea = self.get_idea(idea_id)
        if idea is None:
            raise ArenaError(f"idea {idea_id} does not exist")
        if idea.status == "resolved":
            raise ArenaError("idea is already resolved")
        winner_direction = _normalize_direction(outcome)
        resolver = self.ensure_user(resolver_handle).handle
        profile = self.get_profile(resolver)
        bets = self.bets_for_idea(idea_id)
        winners = [bet for bet in bets if bet.direction == winner_direction]
        losers = [bet for bet in bets if bet.direction != winner_direction]
        losing_pool = sum(bet.amount_fc for bet in losers)
        winner_total = sum(bet.amount_fc for bet in winners)
        payouts = {bet.id: 0 for bet in bets}
        if winner_total > 0:
            ranked = sorted(winners, key=lambda bet: (-bet.amount_fc, bet.placed_ts, bet.id))
            remainder = losing_pool
            for index, bet in enumerate(ranked):
                share = (losing_pool * bet.amount_fc) // winner_total
                payout = bet.amount_fc + share
                payouts[bet.id] = payout
                remainder -= share
                if remainder > 0 and index == len(ranked) - 1:
                    payouts[bet.id] += remainder
                    remainder = 0

        now = int(time.time())
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE ideas
                SET status = 'resolved', resolved_ts = ?, outcome = ?, resolver_handle = ?
                WHERE id = ?
                """,
                (now, winner_direction, resolver, int(idea_id)),
            )
            for bet in bets:
                payout_fc = int(payouts.get(bet.id, 0))
                status = "won" if payout_fc > 0 else "lost"
                conn.execute(
                    "UPDATE bets SET payout_fc = ?, status = ?, settled_ts = ? WHERE id = ?",
                    (payout_fc, status, now, bet.id),
                )
                if payout_fc > 0:
                    self._record_ledger(
                        conn,
                        bet.handle,
                        payout_fc,
                        "bet_settlement",
                        ref_kind="idea",
                        ref_id=int(idea_id),
                        created_ts=now,
                    )
            self._emit_feed_event(
                conn,
                resolver,
                "idea_resolved",
                f"{profile.display_name} resolved idea #{idea_id} as {winner_direction.upper()}",
                idea.title,
                ref_kind="idea",
                ref_id=int(idea_id),
                created_ts=now,
            )
        resolved = self.get_idea(idea_id)
        assert resolved is not None
        return resolved

    # ------------------------------------------------------------------
    # Gold loan system  (replaces the old bankruptcy rescue)
    # ------------------------------------------------------------------

    def borrow_gold(self, handle: str, amount: int = LOAN_MAX_GOLD) -> "Loan":
        """Borrow up to LOAN_MAX_GOLD when balance is exactly 0.

        Rules:
        - Balance must be 0 (you must be completely out).
        - No existing open loan for this handle.
        - Amount capped at LOAN_MAX_GOLD.
        - Interest of LOAN_INTEREST_RATE is pre-calculated and stored;
          total repayment = principal + interest.
        """
        user = self.ensure_user(handle)
        if user.balance_fc != 0:
            raise ArenaError(
                f"Loans are only available at exactly 0 Gold — you still have {user.balance_fc} g."
            )
        borrow_amount = max(1, min(int(amount), LOAN_MAX_GOLD))
        now = int(time.time())
        with closing(self._connect()) as conn, conn:
            open_loan = conn.execute(
                "SELECT id FROM loans WHERE handle = ? AND status = 'open' LIMIT 1",
                (user.handle,),
            ).fetchone()
            if open_loan is not None:
                raise ArenaError(
                    "You already have an open loan. Repay it first before borrowing again."
                )
            interest_fc = int(round(borrow_amount * LOAN_INTEREST_RATE))
            cur = conn.execute(
                """
                INSERT INTO loans(handle, principal_fc, interest_fc, status, borrowed_ts)
                VALUES(?, ?, ?, 'open', ?)
                """,
                (user.handle, borrow_amount, interest_fc, now),
            )
            loan_id = int(cur.lastrowid)
            self._record_ledger(
                conn,
                user.handle,
                borrow_amount,
                "loan_disbursement",
                ref_kind="loan",
                ref_id=loan_id,
                created_ts=now,
            )
        return self._get_loan(loan_id)

    def repay_gold(self, handle: str, amount: Optional[int] = None) -> "Loan":
        """Repay the outstanding open loan (principal + interest).

        If *amount* is None, repays the full outstanding amount.
        Partial repayment is not supported — amount must equal the full debt.
        """
        user = self.ensure_user(handle)
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT * FROM loans WHERE handle = ? AND status = 'open' ORDER BY borrowed_ts ASC LIMIT 1",
                (user.handle,),
            ).fetchone()
            if row is None:
                raise ArenaError("You have no open loan to repay.")
            loan_id = int(row["id"])
            total_owed = int(row["principal_fc"]) + int(row["interest_fc"])
            if amount is not None and int(amount) != total_owed:
                raise ArenaError(
                    f"Repayment must be the full debt: {total_owed} g "
                    f"({row['principal_fc']} principal + {row['interest_fc']} interest)."
                )
            if user.balance_fc < total_owed:
                raise ArenaError(
                    f"Not enough Gold to repay — you owe {total_owed} g but only have {user.balance_fc} g."
                )
            now = int(time.time())
            self._record_ledger(
                conn,
                user.handle,
                -total_owed,
                "loan_repayment",
                ref_kind="loan",
                ref_id=loan_id,
                created_ts=now,
            )
            conn.execute(
                "UPDATE loans SET status = 'repaid', repaid_ts = ? WHERE id = ?",
                (now, loan_id),
            )
        return self._get_loan(loan_id)

    def open_loan(self, handle: str) -> Optional["Loan"]:
        """Return the user's current open loan, or None if they have none."""
        normalized = _normalize_handle(handle)
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM loans WHERE handle = ? AND status = 'open' ORDER BY borrowed_ts ASC LIMIT 1",
                (normalized,),
            ).fetchone()
        return _loan_from_row(row) if row is not None else None

    def _get_loan(self, loan_id: int) -> "Loan":
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
        if row is None:
            raise ArenaError(f"loan {loan_id} does not exist")
        return _loan_from_row(row)

    def rescue(self, handle: str) -> UserAccount:
        """Legacy rescue — kept for test backward-compat; delegates to borrow_gold."""
        loan = self.borrow_gold(handle, BANKRUPTCY_RESCUE_FC)
        return self.ensure_user(handle)

    def leaderboard(self, limit: int = 10) -> List[UserAccount]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT u.handle, u.created_ts, COALESCE(SUM(w.delta_fc), 0) AS balance_fc
                FROM users u
                LEFT JOIN wallet_ledger w ON w.handle = u.handle
                GROUP BY u.handle, u.created_ts
                ORDER BY balance_fc DESC, u.created_ts ASC, u.handle ASC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [
            UserAccount(
                handle=str(row["handle"]),
                balance_fc=int(row["balance_fc"]),
                created_ts=int(row["created_ts"]),
            )
            for row in rows
        ]

    def ledger(self, handle: str, limit: int = 20) -> List[sqlite3.Row]:
        normalized = _normalize_handle(handle)
        with closing(self._connect()) as conn:
            return conn.execute(
                """
                SELECT delta_fc, reason, ref_kind, ref_id, created_ts
                FROM wallet_ledger
                WHERE handle = ?
                ORDER BY created_ts DESC, id DESC
                LIMIT ?
                """,
                (normalized, max(1, int(limit))),
            ).fetchall()

    def _record_ledger(
        self,
        conn: sqlite3.Connection,
        handle: str,
        delta_fc: int,
        reason: str,
        ref_kind: Optional[str] = None,
        ref_id: Optional[int] = None,
        created_ts: Optional[int] = None,
    ) -> None:
        if delta_fc == 0:
            return
        current_balance = conn.execute(
            "SELECT COALESCE(SUM(delta_fc), 0) AS balance_fc FROM wallet_ledger WHERE handle = ?",
            (handle,),
        ).fetchone()
        balance_fc = int(current_balance["balance_fc"] if current_balance is not None else 0)
        next_balance = balance_fc + int(delta_fc)
        if next_balance < 0:
            raise NotEnoughFoxcoin(f"{handle} would go negative ({next_balance} FC)")
        conn.execute(
            """
            INSERT INTO wallet_ledger(handle, delta_fc, reason, ref_kind, ref_id, created_ts)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (handle, int(delta_fc), reason, ref_kind, ref_id, int(created_ts or time.time())),
        )

    def _ensure_profile_row(self, conn: sqlite3.Connection, handle: str, created_ts: int, updated_ts: int) -> None:
        row = conn.execute("SELECT handle FROM profiles WHERE handle = ?", (handle,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO profiles(handle, display_name, bio, created_ts, updated_ts) VALUES(?, ?, '', ?, ?)",
                (handle, handle, int(created_ts), int(updated_ts)),
            )

    def _emit_feed_event(
        self,
        conn: sqlite3.Connection,
        handle: Optional[str],
        event_type: str,
        headline: str,
        body: str,
        ref_kind: Optional[str] = None,
        ref_id: Optional[int] = None,
        created_ts: Optional[int] = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO feed_events(handle, event_type, ref_kind, ref_id, headline, body, created_ts)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (handle, event_type, ref_kind, ref_id, headline.strip(), body.strip(), int(created_ts or time.time())),
        )

    def _require_market_open(self, now_ts: Optional[int] = None) -> MarketSession:
        session = self.market_session(now_ts)
        if not session.is_open:
            opens_at = format_market_timestamp(session.opens_at_ts)
            raise ArenaError(f"NY Fox Exchange is closed. Next open: {opens_at}")
        return session

    def _price_for(self, symbol: str) -> float:
        if self._price_fetcher is not None:
            return float(self._price_fetcher(symbol))
        from ..data import fetch_price

        return float(fetch_price(symbol))


def _normalize_handle(handle: str) -> str:
    normalized = handle.strip().lower()
    if normalized.startswith("@"):
        normalized = normalized[1:]
    if not normalized:
        raise ArenaError("user handle is required")
    return normalized


def _normalize_direction(direction: str) -> str:
    normalized = direction.strip().lower()
    aliases = {"up": "long", "bull": "long", "down": "short", "bear": "short", "flat": "neutral"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in VALID_DIRECTIONS:
        allowed = ", ".join(sorted(VALID_DIRECTIONS))
        raise ArenaError(f"direction must be one of: {allowed}")
    return normalized


def _normalize_trade_direction(direction: str) -> str:
    normalized = _normalize_direction(direction)
    if normalized not in TRADABLE_DIRECTIONS:
        allowed = ", ".join(sorted(TRADABLE_DIRECTIONS))
        raise ArenaError(f"trade direction must be one of: {allowed}")
    return normalized


def _settle_position_amount(amount_fc: int, direction: str, entry_price: float, exit_price: float) -> tuple[int, int]:
    if entry_price <= 0 or exit_price <= 0:
        raise ArenaError("position prices must be positive")
    pct_change = (exit_price - entry_price) / entry_price
    signed_change = pct_change if direction == "long" else -pct_change
    payout_fc = int(round(amount_fc * (1.0 + signed_change)))
    payout_fc = max(0, payout_fc)
    pnl_fc = payout_fc - int(amount_fc)
    return payout_fc, pnl_fc


def _idea_from_row(row: sqlite3.Row) -> Idea:
    return Idea(
        id=int(row["id"]),
        author_handle=str(row["author_handle"]),
        title=str(row["title"]),
        body=str(row["body"]),
        symbol=str(row["symbol"]),
        bias=str(row["bias"]),
        status=str(row["status"]),
        resolution_rule=str(row["resolution_rule"]),
        closes_ts=int(row["closes_ts"]) if row["closes_ts"] is not None else None,
        created_ts=int(row["created_ts"]),
        resolved_ts=int(row["resolved_ts"]) if row["resolved_ts"] is not None else None,
        outcome=str(row["outcome"]) if row["outcome"] is not None else None,
        resolver_handle=str(row["resolver_handle"]) if row["resolver_handle"] is not None else None,
    )


def _bet_from_row(row: sqlite3.Row) -> Bet:
    return Bet(
        id=int(row["id"]),
        idea_id=int(row["idea_id"]),
        handle=str(row["handle"]),
        direction=str(row["direction"]),
        amount_fc=int(row["amount_fc"]),
        payout_fc=int(row["payout_fc"]),
        status=str(row["status"]),
        placed_ts=int(row["placed_ts"]),
        settled_ts=int(row["settled_ts"]) if row["settled_ts"] is not None else None,
    )


def _profile_from_row(row: sqlite3.Row) -> Profile:
    return Profile(
        handle=str(row["handle"]),
        display_name=str(row["display_name"]),
        bio=str(row["bio"]),
        created_ts=int(row["created_ts"]),
        updated_ts=int(row["updated_ts"]),
    )


def _post_from_row(row: sqlite3.Row) -> Post:
    return Post(
        id=int(row["id"]),
        author_handle=str(row["author_handle"]),
        body=str(row["body"]),
        created_ts=int(row["created_ts"]),
    )


def _feed_event_from_row(row: sqlite3.Row) -> FeedEvent:
    return FeedEvent(
        id=int(row["id"]),
        handle=str(row["handle"]) if row["handle"] is not None else None,
        event_type=str(row["event_type"]),
        ref_kind=str(row["ref_kind"]) if row["ref_kind"] is not None else None,
        ref_id=int(row["ref_id"]) if row["ref_id"] is not None else None,
        headline=str(row["headline"]),
        body=str(row["body"]),
        created_ts=int(row["created_ts"]),
    )


def _position_from_row(row: sqlite3.Row) -> Position:
    return Position(
        id=int(row["id"]),
        handle=str(row["handle"]),
        symbol=str(row["symbol"]),
        direction=str(row["direction"]),
        amount_fc=int(row["amount_fc"]),
        entry_price=float(row["entry_price"]),
        exit_price=float(row["exit_price"]) if row["exit_price"] is not None else None,
        status=str(row["status"]),
        realized_pnl_fc=int(row["realized_pnl_fc"]),
        opened_ts=int(row["opened_ts"]),
        closed_ts=int(row["closed_ts"]) if row["closed_ts"] is not None else None,
    )


def _loan_from_row(row: sqlite3.Row) -> "Loan":
    return Loan(
        id=int(row["id"]),
        handle=str(row["handle"]),
        principal_fc=int(row["principal_fc"]),
        interest_fc=int(row["interest_fc"]),
        status=str(row["status"]),
        borrowed_ts=int(row["borrowed_ts"]),
        repaid_ts=int(row["repaid_ts"]) if row["repaid_ts"] is not None else None,
    )


def _default_db_path() -> Path:
    base = Path.home() / ".coinfox"
    return base / "community.sqlite"


def _default_identity_path() -> Path:
    base = Path.home() / ".coinfox"
    return base / "identity"