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
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - exercised only without extras at runtime
    raise RuntimeError("Install API extras first: pip install -e .[api]") from exc

from . import __version__
from .bias import get_bias
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


def _validate_symbol(symbol: str) -> str:
    clean = str(symbol or "").strip().upper().replace("/", "")
    if not clean:
        raise HTTPException(status_code=400, detail="symbol is required")
    if clean in _MAJOR_SYMBOLS:
        return clean
    if clean.endswith(("USD", "USDT")) and 5 <= len(clean) <= 16 and clean[:-3].isalpha():
        return clean
    raise HTTPException(status_code=400, detail=f"Unsupported symbol: {symbol}")
