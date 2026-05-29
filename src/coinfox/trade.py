"""Turn a Verdict into an actionable trade idea — entry, stop, target, size.

Not financial advice. This is a transparent, rules-based suggestion to help
you *think clearly* about a potential move. You still pull the trigger.

Stops/targets are derived from ATR (Average True Range) on the same candles
the verdict used. Position sizing uses a capped fractional-Kelly heuristic
that scales by both probability AND confidence — low confidence = tiny size,
even when probability looks juicy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .data import Candle
from .model import Verdict


@dataclass
class TradeIdea:
    action: str                  # "LONG" | "SHORT" | "STAND ASIDE"
    conviction: str              # "low" | "medium" | "high"
    entry: float
    stop: float
    target: float
    risk_pct: float              # price distance to stop, % of entry
    reward_pct: float            # price distance to target, % of entry
    rr: float                    # reward / risk
    suggested_size_pct: float    # % of bankroll to risk-allocate (capped)
    kelly_fraction: float        # raw Kelly, before cap (informational)
    rationale: str
    horizon_candles: int
    timeframe: str


def _atr(candles: List[Candle], period: int = 14) -> float:
    if len(candles) < period + 1:
        # fallback: high-low of last few candles
        recent = candles[-min(len(candles), 14):]
        return sum(c.high - c.low for c in recent) / max(1, len(recent))
    trs: List[float] = []
    for i in range(1, len(candles)):
        prev_close = candles[i - 1].close
        h, l = candles[i].high, candles[i].low
        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
    # simple moving average of last `period` TRs
    window = trs[-period:]
    return sum(window) / len(window)


def _kelly(p: float, rr: float) -> float:
    """Kelly fraction for a binary bet: f* = (p*(b+1) - 1) / b, b = rr."""
    if rr <= 0:
        return 0.0
    return max(0.0, (p * (rr + 1.0) - 1.0) / rr)


def _conviction(prob_edge: float, confidence: float) -> str:
    score = prob_edge * confidence  # both in [0,1]-ish
    if score >= 0.18:
        return "high"
    if score >= 0.08:
        return "medium"
    return "low"


def make_idea(
    verdict: Verdict,
    candles: List[Candle],
    timeframe: str,
    *,
    atr_stop_mult: float = 1.5,
    atr_target_mult: float = 2.5,
    kelly_cap_pct: float = 2.0,        # never suggest risking more than 2% of bankroll
    kelly_scale: float = 0.25,         # quarter-Kelly is the prudent default
    min_prob_edge: float = 0.06,       # need at least 56/44 to act
    min_confidence: float = 0.35,
) -> TradeIdea:
    entry = verdict.extras["last_close"]
    atr = _atr(candles, 14)
    if atr <= 0:
        atr = entry * 0.005  # 0.5% fallback so we never divide by zero

    p_up = verdict.probability_up
    edge = abs(p_up - 0.5)
    confidence = verdict.confidence

    # Decide direction
    if verdict.bias == "long":
        direction = +1
        action = "LONG"
        p_win = p_up
    elif verdict.bias == "short":
        direction = -1
        action = "SHORT"
        p_win = 1.0 - p_up
    else:
        direction = 0
        action = "STAND ASIDE"
        p_win = max(p_up, 1.0 - p_up)

    stop = entry - direction * atr * atr_stop_mult
    target = entry + direction * atr * atr_target_mult
    risk_abs = abs(entry - stop)
    reward_abs = abs(target - entry)
    risk_pct = (risk_abs / entry) * 100.0 if entry else 0.0
    reward_pct = (reward_abs / entry) * 100.0 if entry else 0.0
    rr = (reward_abs / risk_abs) if risk_abs > 0 else 0.0

    raw_kelly = _kelly(p_win, rr) if direction != 0 else 0.0
    scaled = raw_kelly * kelly_scale
    # Further dampen by confidence (confidence in [0,1])
    scaled *= max(0.0, min(1.0, confidence))
    # Convert "fraction of bankroll to bet" to "% of bankroll to RISK" by multiplying by risk_pct/100
    # but more intuitive: scaled is already what you'd bet; we report it as risk allocation.
    size_pct = max(0.0, min(kelly_cap_pct, scaled * 100.0))

    # Gating: don't suggest acting on weak setups
    gated = False
    if direction != 0 and (edge < min_prob_edge or confidence < min_confidence or rr < 1.0):
        gated = True
        action = "STAND ASIDE"
        size_pct = 0.0

    conviction = _conviction(edge, confidence) if not gated and direction != 0 else "low"

    # Rationale — pick the 3 strongest contributing signals
    contribs = sorted(verdict.signals, key=lambda s: abs(s.vote * s.weight), reverse=True)[:3]
    top_drivers = ", ".join(f"{s.name} ({s.detail})" for s in contribs)
    if action == "STAND ASIDE":
        if gated:
            why = f"edge too small / confidence too low (edge {edge:.2f}, conf {confidence:.2f}, rr {rr:.2f})"
        else:
            why = f"signals neutral (P up {p_up*100:.1f}%); no clear edge"
        rationale = f"Stand aside. {why}. Top drivers: {top_drivers}."
    else:
        rationale = (
            f"{action} bias from confluence: {top_drivers}. "
            f"P(win)={p_win*100:.1f}%, confidence={confidence*100:.1f}%, "
            f"Kelly={raw_kelly*100:.2f}% → scaled to {size_pct:.2f}% bankroll risk."
        )

    return TradeIdea(
        action=action,
        conviction=conviction,
        entry=entry,
        stop=stop if direction != 0 else entry,
        target=target if direction != 0 else entry,
        risk_pct=risk_pct,
        reward_pct=reward_pct,
        rr=rr,
        suggested_size_pct=size_pct,
        kelly_fraction=raw_kelly,
        rationale=rationale,
        horizon_candles=verdict.horizon_candles,
        timeframe=timeframe,
    )
