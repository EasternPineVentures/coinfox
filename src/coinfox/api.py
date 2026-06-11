"""FastAPI surface for mobile and service integrations.

Run locally with:

    python -m coinfox api --port 8000

or:

    uvicorn coinfox.api:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
import time
from importlib import resources
from typing import Optional

try:
    from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - exercised only without extras at runtime
    raise RuntimeError("Install API extras first: pip install -e .[api]") from exc

from . import __version__
from .bias import get_bias
from .community import namegen
from .community.arena import Arena
from .community.market_hours import market_now_text, market_session
from .community.models import ArenaError
from .community.social import SocialError, SocialStore
from .data import DataError, fetch_spot
from .feedback import FeedbackEvent, record_feedback
from .feedback.models import utc_now_iso


CACHE_TTL_SECONDS = 300
DEFAULT_CORS_ORIGINS = (
    "http://localhost:19006",
    "http://127.0.0.1:19006",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "https://coinfox.cloud",
    "https://www.coinfox.cloud",
)
_BIAS_CACHE: dict[tuple[str, str, int, int, bool], tuple[float, dict]] = {}
_MAJOR_SYMBOLS = {
    "AAPL",
    "BTCUSD",
    "BTCUSDT",
    "CL",
    "DIA",
    "DXY",
    "GC",
    "IWM",
    "NVDA",
    "QQQ",
    "SOLUSD",
    "SOLUSDT",
    "SPY",
    "US10Y",
}


app = FastAPI(
    title="CoinFox API",
    version=__version__,
    description=(
        "Free, keyless LONG/SHORT/NEUTRAL market reads from Eastern Pine "
        "Intelligence, an open-source lab from Eastern Pine Ventures."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get("COINFOX_CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


_SOCIAL = SocialStore()
_ARENA = Arena()
# The NY Fox Exchange theme stays visible, but trading is 24/7 by default so the
# app is usable outside NY stock hours. Set COINFOX_NYFE_ENFORCE_HOURS=1 to gate
# trades to the 9:30-4:00 ET weekday session.
_NYFE_ENFORCE_HOURS = os.environ.get("COINFOX_NYFE_ENFORCE_HOURS", "0") == "1"


class _FeedManager:
    """Tracks live WebSocket clients and fans out feed events to them."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for connection in list(self._connections):
            try:
                await connection.send_json(message)
            except Exception:  # pragma: no cover - drop clients that went away
                dead.append(connection)
        for connection in dead:
            self._connections.discard(connection)


_FEED = _FeedManager()


class FeedbackPayload(BaseModel):
    anonymous_user_id: str = Field(..., min_length=1, max_length=128)
    symbol: str = Field(..., min_length=1, max_length=32)
    bias_shown: str = Field(..., min_length=1, max_length=16)
    confidence_shown: float = Field(default=0.0, ge=0.0, le=1.0)
    user_action: Optional[str] = Field(default=None, min_length=1, max_length=64)
    user_feedback: Optional[str] = Field(default=None, min_length=1, max_length=64)
    user_invalidation_level: Optional[float] = None
    comment: str = Field(default="", max_length=1000)
    timestamp: Optional[str] = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "timestamp": utc_now_iso()}


@app.get("/bias")
async def bias(
    symbol: str = Query("BTCUSDT", min_length=1, max_length=32),
    timeframe: str = Query("1h", pattern="^(1m|5m|15m|1h|4h|1d)$"),
    horizon: int = Query(4, ge=1, le=48),
    limit: int = Query(250, ge=60, le=1000),
    use_derivs: bool = False,
) -> dict:
    clean_symbol = _validate_symbol(symbol)
    cache_key = (clean_symbol, timeframe, int(horizon), int(limit), bool(use_derivs))
    cached = _BIAS_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] <= CACHE_TTL_SECONDS:
        return cached[1]

    try:
        payload = get_bias(
            symbol=clean_symbol,
            timeframe=timeframe,
            horizon=horizon,
            limit=limit,
            use_derivs=use_derivs,
        ).as_dict()
    except DataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _BIAS_CACHE[cache_key] = (now, payload)
    return payload


@app.get("/terms")
async def terms() -> dict:
    path = resources.files("coinfox").joinpath("assets", "terms.json")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/feedback")
async def feedback(payload: FeedbackPayload) -> dict:
    action = (payload.user_action or payload.user_feedback or "").strip()
    if not action:
        raise HTTPException(status_code=422, detail="user_action is required")

    try:
        event = FeedbackEvent(
            anonymous_user_id=payload.anonymous_user_id,
            symbol=payload.symbol,
            bias_shown=payload.bias_shown,
            confidence_shown=payload.confidence_shown,
            user_feedback=action,
            user_invalidation_level=payload.user_invalidation_level,
            comment=payload.comment,
            timestamp=payload.timestamp or utc_now_iso(),
        )
        event_id = record_feedback(event)
        return {"ok": True, "id": event_id}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/assets/majors")
async def major_assets() -> dict:
    return {
        "assets": [
            {"symbol": "SPY", "category": "index", "why": "broad US risk appetite"},
            {"symbol": "QQQ", "category": "index", "why": "growth and AI beta"},
            {"symbol": "IWM", "category": "index", "why": "small-cap risk appetite"},
            {"symbol": "NVDA", "category": "mega-cap", "why": "AI risk leader"},
            {"symbol": "AAPL", "category": "mega-cap", "why": "index ballast"},
            {"symbol": "BTCUSDT", "category": "crypto", "why": "24/7 global liquidity pulse"},
            {"symbol": "DXY", "category": "macro", "why": "dollar pressure gauge"},
            {"symbol": "US10Y", "category": "rates", "why": "discount-rate anchor"},
            {"symbol": "GC", "category": "commodity", "why": "real-rate and safety signal"},
            {"symbol": "CL", "category": "commodity", "why": "growth and inflation input"},
        ]
    }


@app.get("/status")
async def status(symbol: Optional[str] = None) -> dict:
    return {
        "ok": True,
        "version": __version__,
        "primary_contract": "LONG_SHORT_NEUTRAL",
        "symbol": symbol,
    }


class CreateUserPayload(BaseModel):
    username: str = Field(..., min_length=1, max_length=40)


class CreatePostPayload(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    direction: str = Field(..., min_length=1, max_length=8)
    entry_price: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    take_profit: float = Field(..., gt=0)
    reasoning: Optional[str] = Field(default=None, max_length=4000)
    chart_image_url: Optional[str] = Field(default=None, max_length=1000)
    foxtrot_score: Optional[float] = None
    regime: Optional[str] = Field(default=None, max_length=64)
    confidence: Optional[float] = None


class GoogleAuthPayload(BaseModel):
    id_token: str = Field(..., min_length=10, max_length=8000)


class CreateDiscussionPayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)
    body: Optional[str] = Field(default=None, max_length=5000)
    topic: Optional[str] = Field(default=None, max_length=32)  # optional tag e.g. BTC, MACRO, FED


class PredictPayload(BaseModel):
    predicted_outcome: str = Field(..., min_length=1, max_length=16)


class CommentPayload(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class VotePayload(BaseModel):
    direction: str = Field(..., min_length=1, max_length=8)  # boost | fade | clear


def _require_user_header(x_user_id: Optional[str]) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="x-user-id header is required")
    return x_user_id


def _enrich_gold(user: dict) -> dict:
    """Show the arena (paper-trading) balance as the user's Gold, so the number
    next to a name reflects their NY Fox Exchange results — one Gold, one truth."""
    try:
        account = _ARENA.get_user(user["username"])
        if account is not None:
            user["gold"] = account.balance_fc
    except Exception:  # pragma: no cover - never let display gold break a response
        pass
    return user


def _enrich_post(post: dict) -> dict:
    if isinstance(post.get("user"), dict):
        _enrich_gold(post["user"])
    return post


def _enrich_comment(comment: dict) -> dict:
    if isinstance(comment.get("user"), dict):
        _enrich_gold(comment["user"])
    return comment


def _arena_handle(user_id: str) -> str:
    """Map a social user id to the arena handle (their username)."""
    try:
        return _SOCIAL.get_user(user_id)["username"]
    except SocialError as exc:
        raise HTTPException(status_code=404, detail="user not found") from exc


def _session_dict() -> dict:
    session = market_session()
    return {
        "is_open": session.is_open,
        "opens_at_ts": session.opens_at_ts,
        "closes_at_ts": session.closes_at_ts,
        "timezone": session.timezone,
        "now_label": market_now_text(),
        "enforced": _NYFE_ENFORCE_HOURS,
    }


def _position_dict(position) -> dict:
    return {
        "id": position.id,
        "symbol": position.symbol,
        "direction": position.direction,
        "amount": position.amount_fc,
        "entry_price": position.entry_price,
        "exit_price": position.exit_price,
        "status": position.status,
        "realized_pnl": position.realized_pnl_fc,
        "opened_ts": position.opened_ts,
        "closed_ts": position.closed_ts,
    }


def _mark_dict(mark) -> dict:
    payload = _position_dict(mark.position)
    payload.update(
        current_price=mark.current_price,
        unrealized_pnl=mark.unrealized_pnl_fc,
        gross_value=mark.gross_value_fc,
    )
    return payload


def _stats_dict(stats) -> dict:
    return {
        "handle": stats.handle,
        "balance": stats.balance_fc,
        "open_positions": stats.open_positions,
        "closed_positions": stats.closed_positions,
        "winning_positions": stats.winning_positions,
        "losing_positions": stats.losing_positions,
        "realized_pnl": stats.realized_pnl_fc,
        "unrealized_pnl": stats.unrealized_pnl_fc,
        "total_staked": stats.total_staked_fc,
    }


@app.get("/api/username/suggest")
async def suggest_usernames(count: int = Query(5, ge=1, le=20)) -> dict:
    return {"suggestions": namegen.suggest_batch(count)}


@app.post("/api/users")
async def create_user(payload: CreateUserPayload) -> dict:
    try:
        user = _SOCIAL.create_user(payload.username)
    except SocialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Provision the NY Fox Exchange account (grants starting Gold).
    try:
        _ARENA.ensure_user(user["username"])
    except Exception:  # pragma: no cover - never block signup on arena setup
        pass
    return _enrich_gold(user)


@app.get("/api/users/{user_id}")
async def get_user(user_id: str) -> dict:
    try:
        return _enrich_gold(_SOCIAL.get_user(user_id))
    except SocialError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/posts")
async def list_posts(
    limit: int = Query(50, ge=1, le=200),
    x_user_id: Optional[str] = Header(default=None),
) -> list:
    return [_enrich_post(post) for post in _SOCIAL.list_posts(viewer_id=x_user_id, limit=limit)]


@app.get("/api/feed")
async def ranked_feed(
    limit: int = Query(50, ge=1, le=200),
    x_user_id: Optional[str] = Header(default=None),
) -> list:
    """Proof-ranked FYP feed. New/anonymous visitors land here: the most
    credible, fresh, well-argued calls first (not just the newest)."""
    return [_enrich_post(post) for post in _SOCIAL.list_feed_ranked(viewer_id=x_user_id, limit=limit)]


@app.get("/api/price/{symbol}")
async def live_price(symbol: str) -> dict:
    """Live spot price for a symbol. Crypto pairs (e.g. BTCUSDT, ETHUSDT) resolve
    via Binance/Kraken/Coinbase. Equities aren't wired yet — they return
    ``price: null`` rather than an error, so callers can degrade gracefully."""
    clean = str(symbol or "").strip().upper()
    try:
        price = fetch_spot(clean)
    except DataError:
        return {"symbol": clean, "price": None, "source": None}
    return {"symbol": clean, "price": price, "source": "live"}


@app.get("/api/users/{user_id}/track-record")
async def user_track_record(user_id: str) -> dict:
    try:
        return _SOCIAL.author_track_record(user_id)
    except SocialError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/posts")
async def create_post(
    payload: CreatePostPayload,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    user_id = _require_user_header(x_user_id)
    try:
        post = _SOCIAL.create_post(user_id, payload.model_dump())
    except SocialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _FEED.broadcast({"type": "new_post", "post_id": post["id"], "user_id": user_id})
    return _enrich_post(post)


@app.post("/api/auth/google")
async def auth_google(payload: GoogleAuthPayload) -> dict:
    """Sign in with Google. The app sends Google's ID token; we verify it with
    Google, confirm it was issued for OUR app, then find-or-create the account."""
    import requests

    # Accept any of our configured client IDs (web / android / ios all differ).
    allowed_auds = {
        aud.strip()
        for aud in os.environ.get("GOOGLE_CLIENT_ID", "").split(",")
        if aud.strip()
    }
    try:
        resp = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": payload.id_token},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Could not reach Google") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    info = resp.json()
    # Guard against tokens minted for a different app.
    if allowed_auds and info.get("aud") not in allowed_auds:
        raise HTTPException(status_code=401, detail="Token was not issued for CoinFox")
    sub = info.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Google token missing subject")
    user = _SOCIAL.find_or_create_oauth_user(
        "google", sub, email=info.get("email"), suggested_username=info.get("given_name")
    )
    return _enrich_gold(user)


@app.post("/api/discussions")
async def create_discussion(
    payload: CreateDiscussionPayload,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    user_id = _require_user_header(x_user_id)
    try:
        post = _SOCIAL.create_discussion(user_id, payload.model_dump())
    except SocialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _FEED.broadcast({"type": "new_post", "post_id": post["id"], "user_id": user_id})
    return _enrich_post(post)


@app.post("/api/posts/{post_id}/predict")
async def predict_post(
    post_id: str,
    payload: PredictPayload,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    user_id = _require_user_header(x_user_id)
    try:
        result = _SOCIAL.predict(user_id, post_id, payload.predicted_outcome)
    except SocialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _FEED.broadcast(
        {
            "type": "new_prediction",
            "post_id": post_id,
            "user_id": user_id,
            "outcome": payload.predicted_outcome,
        }
    )
    return result


@app.post("/api/posts/{post_id}/vote")
async def vote_post(
    post_id: str,
    payload: VotePayload,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    user_id = _require_user_header(x_user_id)
    try:
        result = _SOCIAL.vote(user_id, post_id, payload.direction)
    except SocialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Carry the new score so every viewer's feed can update the count live,
    # without anyone needing to refetch.
    await _FEED.broadcast(
        {"type": "new_vote", "post_id": post_id, "user_id": user_id, "score": result.get("score")}
    )
    return result


@app.get("/api/posts/{post_id}/comments")
async def list_comments(
    post_id: str,
    x_user_id: Optional[str] = Header(default=None),
) -> list:
    return [_enrich_comment(comment) for comment in _SOCIAL.list_comments(post_id, viewer_id=x_user_id)]


@app.post("/api/comments/{comment_id}/vote")
async def vote_comment(
    comment_id: str,
    payload: VotePayload,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    user_id = _require_user_header(x_user_id)
    try:
        result = _SOCIAL.vote_comment(user_id, comment_id, payload.direction)
    except SocialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _FEED.broadcast(
        {"type": "comment_vote", "comment_id": comment_id, "score": result.get("score")}
    )
    return result


@app.post("/api/posts/{post_id}/comments")
async def add_comment(
    post_id: str,
    payload: CommentPayload,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    user_id = _require_user_header(x_user_id)
    try:
        comment = _SOCIAL.add_comment(user_id, post_id, payload.content)
    except SocialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _FEED.broadcast(
        {"type": "new_comment", "post_id": post_id, "user_id": user_id}
    )
    return _enrich_comment(comment)


# ---------------------------------------------------------------------------
# NY Fox Exchange — paper trading (play-money Gold, live prices)
# ---------------------------------------------------------------------------
class OpenPositionPayload(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    direction: str = Field(..., min_length=1, max_length=8)
    amount: int = Field(..., gt=0, le=1_000_000)


@app.get("/api/exchange/session")
async def exchange_session() -> dict:
    return _session_dict()


@app.get("/api/exchange/positions")
async def exchange_positions(
    status: Optional[str] = Query(default=None, pattern="^(open|closed)$"),
    limit: int = Query(50, ge=1, le=200),
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    handle = _arena_handle(_require_user_header(x_user_id))
    marks = _ARENA.marked_positions(handle=handle, status=status, limit=limit)
    return {
        "session": _session_dict(),
        "stats": _stats_dict(_ARENA.user_stats(handle)),
        "positions": [_mark_dict(mark) for mark in marks],
    }


@app.post("/api/exchange/positions")
async def exchange_open_position(
    payload: OpenPositionPayload,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    handle = _arena_handle(_require_user_header(x_user_id))
    try:
        position = _ARENA.open_position(
            handle,
            payload.symbol,
            payload.direction,
            payload.amount,
            enforce_market_hours=_NYFE_ENFORCE_HOURS,
        )
    except ArenaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - price feed / data issues
        raise HTTPException(status_code=502, detail=f"could not price {payload.symbol}: {exc}") from exc
    await _FEED.broadcast({"type": "position_open", "user_id": x_user_id})
    return _position_dict(position)


@app.post("/api/exchange/positions/{position_id}/close")
async def exchange_close_position(
    position_id: int,
    x_user_id: Optional[str] = Header(default=None),
) -> dict:
    handle = _arena_handle(_require_user_header(x_user_id))
    try:
        position = _ARENA.close_position(
            position_id,
            handle,
            enforce_market_hours=_NYFE_ENFORCE_HOURS,
        )
    except ArenaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - price feed / data issues
        raise HTTPException(status_code=502, detail=f"could not close position: {exc}") from exc
    await _FEED.broadcast({"type": "position_close", "user_id": x_user_id})
    return _position_dict(position)


@app.get("/api/exchange/leaderboard")
async def exchange_leaderboard(limit: int = Query(10, ge=1, le=50)) -> dict:
    return {"leaders": [_stats_dict(stat) for stat in _ARENA.stats_leaderboard(limit)]}


@app.websocket("/ws/feed")
async def feed_socket(websocket: WebSocket) -> None:
    await _FEED.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _FEED.disconnect(websocket)
    except Exception:  # pragma: no cover - ensure cleanup on any socket error
        _FEED.disconnect(websocket)


def _validate_symbol(symbol: str) -> str:
    clean = str(symbol or "").strip().upper().replace("/", "")
    if not clean:
        raise HTTPException(status_code=400, detail="symbol is required")
    if clean in _MAJOR_SYMBOLS:
        return clean
    if clean.endswith(("USD", "USDT")) and 5 <= len(clean) <= 16 and clean[:-3].isalpha():
        return clean
    raise HTTPException(status_code=400, detail=f"Unsupported symbol: {symbol}")
