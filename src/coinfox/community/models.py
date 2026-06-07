"""Domain dataclasses and exceptions for the NY Fox Exchange community arena."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ArenaError(ValueError):
    """Raised when a community action cannot be completed."""


class NotEnoughGold(ArenaError):
    """Raised when a user tries to spend more Gold than they have."""


# backward-compat alias so existing imports still work
NotEnoughFoxcoin = NotEnoughGold


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Loan:
    id: int
    handle: str
    principal_fc: int          # remaining principal still owed
    interest_fc: int           # accrued interest still owed
    status: str                # 'open' | 'repaid'
    borrowed_ts: int
    last_settled_ts: int       # last weekly accrual/auto-repay boundary
    repaid_ts: Optional[int]

    @property
    def total_owed_fc(self) -> int:
        return self.principal_fc + self.interest_fc


@dataclass(frozen=True)
class UserAccount:
    handle: str
    balance_fc: int
    created_ts: int


@dataclass(frozen=True)
class Profile:
    handle: str
    display_name: str
    bio: str
    created_ts: int
    updated_ts: int


@dataclass(frozen=True)
class MarketSession:
    is_open: bool
    opens_at_ts: int
    closes_at_ts: int
    timezone: str = "America/New_York"


@dataclass(frozen=True)
class Idea:
    id: int
    author_handle: str
    title: str
    body: str
    symbol: str
    bias: str
    status: str
    resolution_rule: str
    closes_ts: Optional[int]
    created_ts: int
    resolved_ts: Optional[int]
    outcome: Optional[str]
    resolver_handle: Optional[str]


@dataclass(frozen=True)
class Comment:
    id: int
    idea_id: int
    author_handle: str
    body: str
    created_ts: int


@dataclass(frozen=True)
class Bet:
    id: int
    idea_id: int
    handle: str
    direction: str
    amount_fc: int
    payout_fc: int
    status: str
    placed_ts: int
    settled_ts: Optional[int]


@dataclass(frozen=True)
class Position:
    id: int
    handle: str
    symbol: str
    direction: str
    amount_fc: int
    entry_price: float
    exit_price: Optional[float]
    status: str
    realized_pnl_fc: int
    opened_ts: int
    closed_ts: Optional[int]


@dataclass(frozen=True)
class PositionMark:
    position: Position
    current_price: Optional[float]
    unrealized_pnl_fc: Optional[int]
    gross_value_fc: Optional[int]


@dataclass(frozen=True)
class UserStats:
    handle: str
    balance_fc: int
    open_positions: int
    closed_positions: int
    winning_positions: int
    losing_positions: int
    realized_pnl_fc: int
    unrealized_pnl_fc: int
    total_staked_fc: int


@dataclass(frozen=True)
class Post:
    id: int
    author_handle: str
    body: str
    created_ts: int


@dataclass(frozen=True)
class FeedEvent:
    id: int
    handle: Optional[str]
    event_type: str
    ref_kind: Optional[str]
    ref_id: Optional[int]
    headline: str
    body: str
    created_ts: int
