"""Confluence-based probability model.

Each signal contributes a vote in [-1, +1] with a weight. Votes are summed,
squashed through a logistic, and reported as P(up over the next `horizon`
candles). Confidence reflects signal agreement.

All weights are explicit and tweakable. This is a transparent heuristic,
not a trained model — community PRs to tune or extend it are welcome.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .data import Candle, FearGreed
from .indicators import bollinger, ema, macd, rsi, slope, volume_zscore


@dataclass
class Signal:
    name: str
    vote: float
    weight: float
    detail: str = ""


@dataclass
class Verdict:
    probability_up: float
    confidence: float
    bias: str
    horizon_candles: int
    signals: List[Signal] = field(default_factory=list)
    extras: Dict[str, float] = field(default_factory=dict)


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# Default weights — tweak freely. See CONTRIBUTING.md for guidance.
WEIGHTS = {
    "trend_ema":   1.4,
    "trend_slope": 0.9,
    "rsi":         1.0,
    "macd":        1.2,
    "bbands":      0.8,
    "volume":      0.6,
    "sentiment":   0.7,
    "funding":     0.8,   # derivatives funding rate (contrarian on extremes)
    "basis":       0.5,   # perp basis vs spot
    "ai_context":  0.6,   # Stored AI context signal (gated on freshness + conviction)
}

# AI signal is only trusted if younger than this
_AI_MAX_AGE_S = 1800  # 30 minutes


def _read_ai_signal() -> Optional[Signal]:
    """Try to read the latest stored AI market read from SQLite. Fails gracefully."""
    try:
        from pathlib import Path
        import sqlite3
        db = Path.home() / ".coinfox" / "churn.sqlite"
        if not db.exists():
            return None
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT ts, bias, conviction FROM thoughts ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        ts, bias, conviction = row
        age_s = int(time.time()) - int(ts)
        if age_s > _AI_MAX_AGE_S:
            return None  # stale — don't influence the model
        bias_vote = {"long": 1.0, "short": -1.0, "neutral": 0.0}.get(str(bias).lower(), 0.0)
        # Scale by conviction (1-5 → 0.2-1.0)
        conv_scale = max(1, min(5, int(conviction))) / 5.0
        vote = bias_vote * conv_scale
        age_str = f"{age_s // 60}m ago" if age_s >= 60 else f"{age_s}s ago"
        detail = f"context {bias} conv={conviction}/5 ({age_str})"
        return Signal("ai_context", vote, WEIGHTS["ai_context"], detail)
    except Exception:
        return None


def evaluate(
    candles: List[Candle],
    fng: Optional[FearGreed],
    horizon: int = 4,
    funding_rate: Optional[float] = None,        # 8h rate, e.g. 0.0001
    basis_pct: Optional[float] = None,           # perp mark vs index, %
) -> Verdict:
    if len(candles) < 60:
        raise ValueError("Need at least ~60 candles for a reliable read")

    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]

    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200) if len(closes) >= 200 else ema(closes, min(100, len(closes)))
    rsi14 = rsi(closes, 14)
    m = macd(closes)
    bb = bollinger(closes, 20, 2.0)
    vz = volume_zscore(volumes, 20)

    last_close = closes[-1]
    signals: List[Signal] = []

    # Trend: EMA alignment
    e20, e50, e200 = ema20[-1], ema50[-1], ema200[-1]
    if e20 > e50 > e200:
        align_vote, align_detail = 1.0, "EMA20>50>200 (uptrend stack)"
    elif e20 < e50 < e200:
        align_vote, align_detail = -1.0, "EMA20<50<200 (downtrend stack)"
    else:
        align_vote = 0.5 if e20 > e50 else -0.5
        align_detail = f"mixed stack (EMA20 {'>' if e20 > e50 else '<'} EMA50)"
    signals.append(Signal("trend_ema", align_vote, WEIGHTS["trend_ema"], align_detail))

    # Trend slope
    s50 = slope(ema50, lookback=5)
    signals.append(Signal("trend_slope", _clamp(s50 * 400.0),
                          WEIGHTS["trend_slope"], f"EMA50 slope {s50:+.4%}/bar"))

    # RSI
    r = rsi14[-1]
    if r != r:
        rsi_vote, rsi_detail = 0.0, "RSI n/a"
    elif r >= 70:
        rsi_vote, rsi_detail = -0.7, f"RSI {r:.1f} overbought"
    elif r <= 30:
        rsi_vote, rsi_detail = 0.7, f"RSI {r:.1f} oversold"
    else:
        rsi_vote = _clamp((r - 50.0) / 25.0)
        rsi_detail = f"RSI {r:.1f}"
    signals.append(Signal("rsi", rsi_vote, WEIGHTS["rsi"], rsi_detail))

    # MACD
    h = m.hist[-1]
    h_prev = m.hist[-2] if len(m.hist) >= 2 else h
    h_norm = h / last_close if last_close else 0.0
    signals.append(Signal("macd", _clamp(h_norm * 2000.0),
                          WEIGHTS["macd"],
                          f"hist {h:+.2f} {'rising' if h > h_prev else 'falling'}"))

    # Bollinger %B
    pb = bb.pct_b[-1]
    if pb != pb:
        bb_vote, bb_detail = 0.0, "BB n/a"
    elif pb >= 1.0:
        bb_vote, bb_detail = -0.6, f"%B {pb:.2f} above upper"
    elif pb <= 0.0:
        bb_vote, bb_detail = 0.6, f"%B {pb:.2f} below lower"
    else:
        bb_vote = _clamp((0.5 - pb) * 1.2)
        bb_detail = f"%B {pb:.2f}"
    signals.append(Signal("bbands", bb_vote, WEIGHTS["bbands"], bb_detail))

    # Volume
    vzl = vz[-1]
    if vzl != vzl:
        vol_vote, vol_detail = 0.0, "vol z n/a"
    else:
        last_dir = 1.0 if closes[-1] >= candles[-1].open else -1.0
        vol_vote = _clamp(last_dir * (vzl / 2.5))
        vol_detail = f"vol z {vzl:+.2f} on {'green' if last_dir > 0 else 'red'} bar"
    signals.append(Signal("volume", vol_vote, WEIGHTS["volume"], vol_detail))

    # Sentiment (Fear & Greed — contrarian on extremes)
    if fng is None:
        signals.append(Signal("sentiment", 0.0, WEIGHTS["sentiment"], "F&G unavailable"))
    else:
        v = fng.value
        if v <= 20:
            sent_vote = 0.6
        elif v >= 80:
            sent_vote = -0.6
        else:
            sent_vote = _clamp((v - 50) / 60.0)
        signals.append(Signal("sentiment", sent_vote, WEIGHTS["sentiment"],
                              f"F&G {v} ({fng.classification})"))

    # Funding rate — extreme positive funding = crowded longs = bearish lean
    if funding_rate is not None:
        fr_vote = _clamp(-funding_rate * 1500.0)
        signals.append(Signal("funding", fr_vote, WEIGHTS["funding"],
                              f"perp funding {funding_rate*100:+.4f}%/8h"))
    # else: omit entirely so absent data doesn't dilute weight

    # Basis — perp trading at premium to spot = bullish positioning
    if basis_pct is not None:
        signals.append(Signal("basis", _clamp(basis_pct * 5.0), WEIGHTS["basis"],
                              f"perp basis {basis_pct:+.3f}%"))

    # AI context signal - reads latest stored market read (fresh only)
    ai_sig = _read_ai_signal()
    if ai_sig is not None:
        signals.append(ai_sig)

    # Aggregate
    total_w = sum(s.weight for s in signals) or 1.0
    weighted_sum = sum(s.vote * s.weight for s in signals)
    norm = weighted_sum / total_w

    horizon_scale = 1.0 / (1.0 + 0.15 * max(0, horizon - 1))
    prob = _logistic(2.2 * norm * horizon_scale)

    mean_vote = weighted_sum / total_w
    dispersion = sum(s.weight * (s.vote - mean_vote) ** 2 for s in signals) / total_w
    agreement = max(0.0, 1.0 - dispersion)
    magnitude = min(1.0, abs(norm) * 1.8)
    confidence = 0.5 * agreement + 0.5 * magnitude

    if prob >= 0.58:
        bias = "long"
    elif prob <= 0.42:
        bias = "short"
    else:
        bias = "neutral"

    return Verdict(
        probability_up=prob,
        confidence=confidence,
        bias=bias,
        horizon_candles=horizon,
        signals=signals,
        extras={
            "last_close": last_close,
            "ema20": e20, "ema50": e50, "ema200": e200,
            "rsi14": r, "macd_hist": h, "pct_b": pb, "vol_z": vzl,
            "norm_score": norm,
        },
    )
