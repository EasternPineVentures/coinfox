"""First-class LONG/SHORT/NEUTRAL bias reads for CoinFox-facing products."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .data import DataError, fetch_24h_stats, fetch_fear_greed, fetch_klines, fetch_price
from .model import Signal, Verdict, evaluate


BIAS_LONG_THRESHOLD = 0.58
BIAS_SHORT_THRESHOLD = 0.42


@dataclass(frozen=True)
class InvalidationRule:
    type: str
    level: Optional[float]
    reason: str
    label: str = "Thesis check"
    not_a_stop_loss: bool = True

    def as_dict(self) -> Dict[str, object]:
        return {
            "type": self.type,
            "level": self.level,
            "reason": self.reason,
            "label": self.label,
            "not_a_stop_loss": self.not_a_stop_loss,
        }


@dataclass(frozen=True)
class SourceHealth:
    status: str
    stale_sources: List[str]
    notes: List[str]

    def as_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "stale_sources": self.stale_sources,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class BiasRead:
    symbol: str
    timeframe: str
    horizon: int
    bias: str
    conviction: float
    invalidation: InvalidationRule
    human_readable: str
    probability_up: float
    probability_down: float
    confidence: float
    price: Optional[float]
    change_24h_pct: Optional[float]
    regime_hint: str
    updated_at: str
    drivers: List[Dict[str, object]]
    source_health: SourceHealth

    def as_dict(self) -> Dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "horizon": self.horizon,
            "bias": self.bias,
            "conviction": self.conviction,
            "thesis": self.human_readable,
            "invalidation": self.invalidation.as_dict() if self.bias != "NEUTRAL" else None,
            "human_readable": self.human_readable,
            "probability_up": self.probability_up,
            "probability_down": self.probability_down,
            "confidence": self.confidence,
            "price": self.price,
            "change_24h_pct": self.change_24h_pct,
            "regime_hint": self.regime_hint,
            "updated_at": self.updated_at,
            "timestamp": self.updated_at,
            "drivers": self.drivers,
            "source_health": self.source_health.as_dict(),
        }


def read_bias(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    horizon: int = 4,
    limit: int = 250,
    use_derivs: bool = False,
) -> BiasRead:
    """Fetch market context and return the product-level CoinFox bias.

    The public contract is deliberately simple: LONG, SHORT, or NEUTRAL.
    Details remain available for users who want the why, but the top-line
    answer should be fast and unambiguous.
    """

    clean_symbol = _normalize_symbol(symbol)
    health = _HealthBuilder()
    candles = fetch_klines(clean_symbol, interval=timeframe, limit=limit)
    health.ok("klines")
    price = _try_price(clean_symbol, health)
    change_24h_pct = _try_24h_change(clean_symbol, health)
    fng = fetch_fear_greed()
    health.ok("fear_greed")

    funding = basis = None
    if use_derivs:
        try:
            from .sources.derivatives import fetch_derivatives

            derivatives = fetch_derivatives()
            funding = derivatives.avg_funding
            basis = derivatives.basis_pct
            health.ok("derivatives")
        except Exception:
            funding = basis = None
            health.stale("derivatives", "Derivatives context was unavailable; bias still uses spot and sentiment inputs.")

    verdict = evaluate(
        candles,
        fng,
        horizon=max(1, int(horizon)),
        funding_rate=funding,
        basis_pct=basis,
    )
    return from_verdict(
        clean_symbol,
        timeframe=timeframe,
        horizon=max(1, int(horizon)),
        verdict=verdict,
        price=price,
        change_24h_pct=change_24h_pct,
        source_health=health.as_source_health(),
    )


def get_bias(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    horizon: int = 4,
    limit: int = 250,
    use_derivs: bool = False,
) -> BiasRead:
    """Public bias function shared by CLI and API surfaces."""
    return read_bias(
        symbol=symbol,
        timeframe=timeframe,
        horizon=horizon,
        limit=limit,
        use_derivs=use_derivs,
    )


def from_verdict(
    symbol: str,
    timeframe: str,
    horizon: int,
    verdict: Verdict,
    price: Optional[float] = None,
    change_24h_pct: Optional[float] = None,
    source_health: Optional[SourceHealth] = None,
) -> BiasRead:
    prob_up = _round_probability(verdict.probability_up)
    confidence = _round_probability(verdict.confidence)
    bias = bias_label(verdict.probability_up)
    clean_symbol = _normalize_symbol(symbol)
    invalidation = _invalidation_rule(bias, verdict, price)
    drivers = [_signal_driver(signal) for signal in _top_signals(verdict.signals)]
    return BiasRead(
        symbol=clean_symbol,
        timeframe=timeframe,
        horizon=max(1, int(horizon)),
        bias=bias,
        conviction=confidence,
        invalidation=invalidation,
        human_readable=_human_readable(clean_symbol, bias, invalidation, drivers),
        probability_up=prob_up,
        probability_down=_round_probability(1.0 - verdict.probability_up),
        confidence=confidence,
        price=price,
        change_24h_pct=change_24h_pct,
        regime_hint=_regime_hint(bias, confidence),
        updated_at=datetime.now(timezone.utc).isoformat(),
        drivers=drivers,
        source_health=source_health or SourceHealth(status="healthy", stale_sources=[], notes=[]),
    )


def bias_label(probability_up: float) -> str:
    if probability_up >= BIAS_LONG_THRESHOLD:
        return "LONG"
    if probability_up <= BIAS_SHORT_THRESHOLD:
        return "SHORT"
    return "NEUTRAL"


def compute_invalidation(
    bias: str,
    current_price: float,
    recent_swing_high: float,
    recent_swing_low: float,
    buffer_percent: float = 0.005,
) -> Optional[InvalidationRule]:
    """Compute a first-pass thesis invalidation area from recent swing levels."""
    clean_bias = str(bias or "").upper()
    if not all(_is_number(v) for v in (current_price, recent_swing_high, recent_swing_low)):
        return None

    buffer = float(current_price) * max(0.0, float(buffer_percent))
    if clean_bias == "SHORT":
        return InvalidationRule(
            type="price_above",
            level=_round_level(float(recent_swing_high) + buffer),
            reason=(
                "Price moving above this area would weaken the short thesis "
                "because it breaks above recent resistance."
            ),
            label="Thesis weakens above",
        )
    if clean_bias == "LONG":
        return InvalidationRule(
            type="price_below",
            level=_round_level(float(recent_swing_low) - buffer),
            reason=(
                "Price moving below this area would weaken the long thesis "
                "because it breaks below recent support."
            ),
            label="Thesis weakens below",
        )
    return None


def _normalize_symbol(symbol: str) -> str:
    clean = (symbol or "").strip().upper().replace("/", "")
    if not clean:
        raise DataError("symbol is required")
    return clean


class _HealthBuilder:
    def __init__(self) -> None:
        self._stale: List[str] = []
        self._notes: List[str] = []

    def ok(self, _name: str) -> None:
        return None

    def stale(self, name: str, note: str) -> None:
        if name not in self._stale:
            self._stale.append(name)
        self._notes.append(note)

    def as_source_health(self) -> SourceHealth:
        if not self._stale:
            return SourceHealth(status="healthy", stale_sources=[], notes=[])
        return SourceHealth(
            status="degraded",
            stale_sources=sorted(self._stale),
            notes=self._notes,
        )


def _try_price(symbol: str, health: Optional[_HealthBuilder] = None) -> Optional[float]:
    try:
        return float(fetch_price(symbol))
    except Exception:
        if health:
            health.stale("price", "Live price was unavailable; CoinFox fell back to candle context where possible.")
        return None


def _try_24h_change(symbol: str, health: Optional[_HealthBuilder] = None) -> Optional[float]:
    try:
        stats = fetch_24h_stats(symbol)
        return float(stats.get("priceChangePercent"))
    except Exception:
        if health:
            health.stale("24h_stats", "24h change was unavailable; the read still uses available market signals.")
        return None


def _round_probability(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _round_level(value: float) -> float:
    if abs(value) >= 100:
        return round(value, 2)
    if abs(value) >= 1:
        return round(value, 4)
    return round(value, 8)


def _invalidation_rule(bias: str, verdict: Verdict, price: Optional[float]) -> InvalidationRule:
    ref_price = _reference_price(verdict, price)
    ema200 = verdict.extras.get("ema200")
    numeric_refs = [float(v) for v in (ref_price, ema200) if _is_number(v)]
    recent_swing_high = max(numeric_refs)
    recent_swing_low = min(numeric_refs)
    computed = compute_invalidation(bias, ref_price, recent_swing_high, recent_swing_low)
    if computed:
        return computed

    return InvalidationRule(
        type="none",
        level=None,
        reason="No directional setup is active while the read is neutral",
        label="No active thesis check",
    )


def _reference_price(verdict: Verdict, price: Optional[float]) -> float:
    if _is_number(price):
        return float(price)
    last_close = verdict.extras.get("last_close")
    if _is_number(last_close):
        return float(last_close)
    return 1.0


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _human_readable(
    symbol: str,
    bias: str,
    invalidation: InvalidationRule,
    drivers: List[Dict[str, object]],
) -> str:
    if bias == "NEUTRAL":
        return (
            f"NEUTRAL on {symbol} because signals are mixed. "
            "No directional thesis check is active until the model leaves neutral."
        )

    direction = "long" if bias == "LONG" else "short"
    setup = "bullish" if bias == "LONG" else "bearish"
    close_word = "below" if bias == "LONG" else "above"
    level = f"${invalidation.level:,.2f}" if isinstance(invalidation.level, (int, float)) else "the invalidation level"
    reason = _driver_reason(drivers)
    return (
        f"{bias} on {symbol} because {reason}. "
        f"The {direction} thesis weakens if price closes {close_word} {level}, "
        f"because that would invalidate the {setup} setup."
    )


def _driver_reason(drivers: List[Dict[str, object]]) -> str:
    if not drivers:
        return "the model has a directional edge"
    top = drivers[0]
    detail = str(top.get("detail") or "").strip()
    name = str(top.get("name") or "top signal").replace("_", " ")
    if detail:
        return detail
    return f"{name} is the strongest driver"


def _regime_hint(bias: str, confidence: float) -> str:
    if bias == "NEUTRAL":
        return "mixed"
    if confidence >= 0.65:
        return "high-conviction"
    if confidence >= 0.4:
        return "watchable"
    return "fragile"


def _top_signals(signals: List[Signal], limit: int = 5) -> List[Signal]:
    return sorted(signals, key=lambda signal: abs(signal.vote * signal.weight), reverse=True)[:limit]


def _signal_driver(signal: Signal) -> Dict[str, object]:
    contribution = signal.vote * signal.weight
    if contribution > 0.05:
        lean = "LONG"
        impact = "bullish"
    elif contribution < -0.05:
        lean = "SHORT"
        impact = "bearish"
    else:
        lean = "NEUTRAL"
        impact = "neutral"
    return {
        "name": signal.name,
        "lean": lean,
        "impact": impact,
        "vote": round(float(signal.vote), 4),
        "weight": round(float(signal.weight), 4),
        "contribution": round(float(contribution), 4),
        "detail": signal.detail,
        "plain_english": signal.detail or f"{signal.name.replace('_', ' ')} is {impact}.",
    }
