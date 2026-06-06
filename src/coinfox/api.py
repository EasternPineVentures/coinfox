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
from .community.social import SocialError, SocialStore
from .data import DataError
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


class PredictPayload(BaseModel):
    predicted_outcome: str = Field(..., min_length=1, max_length=16)


class CommentPayload(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


def _require_user_header(x_user_id: Optional[str]) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="x-user-id header is required")
    return x_user_id


@app.get("/api/username/suggest")
async def suggest_usernames(count: int = Query(5, ge=1, le=20)) -> dict:
    return {"suggestions": namegen.suggest_batch(count)}


@app.post("/api/users")
async def create_user(payload: CreateUserPayload) -> dict:
    try:
        return _SOCIAL.create_user(payload.username)
    except SocialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/users/{user_id}")
async def get_user(user_id: str) -> dict:
    try:
        return _SOCIAL.get_user(user_id)
    except SocialError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/posts")
async def list_posts(
    limit: int = Query(50, ge=1, le=200),
    x_user_id: Optional[str] = Header(default=None),
) -> list:
    return _SOCIAL.list_posts(viewer_id=x_user_id, limit=limit)


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
    return post


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


@app.get("/api/posts/{post_id}/comments")
async def list_comments(post_id: str) -> list:
    return _SOCIAL.list_comments(post_id)


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
    return comment


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
