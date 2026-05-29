"""Pure-Python technical indicators. No pandas/numpy dependency."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


def ema(values: Sequence[float], period: int) -> List[float]:
    if period <= 0:
        raise ValueError("period must be positive")
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    out = [float(values[0])]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1.0 - k))
    return out


def sma(values: Sequence[float], period: int) -> List[float]:
    out: List[float] = []
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= period:
            s -= values[i - period]
        out.append(s / period if i >= period - 1 else float("nan"))
    return out


def stdev(values: Sequence[float], period: int) -> List[float]:
    out: List[float] = []
    for i in range(len(values)):
        if i < period - 1:
            out.append(float("nan"))
            continue
        window = values[i - period + 1 : i + 1]
        m = sum(window) / period
        var = sum((x - m) ** 2 for x in window) / period
        out.append(var ** 0.5)
    return out


def rsi(closes: Sequence[float], period: int = 14) -> List[float]:
    if len(closes) < period + 1:
        return [float("nan")] * len(closes)
    gains, losses = [0.0], [0.0]
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period
    out = [float("nan")] * period
    rs = avg_gain / avg_loss if avg_loss > 0 else float("inf")
    out.append(100.0 - 100.0 / (1.0 + rs))
    for i in range(period + 1, len(closes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            out.append(100.0)
        else:
            rs = avg_gain / avg_loss
            out.append(100.0 - 100.0 / (1.0 + rs))
    return out


@dataclass
class MACDResult:
    macd: List[float]
    signal: List[float]
    hist: List[float]


def macd(closes: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9) -> MACDResult:
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line, signal)
    hist = [m - s for m, s in zip(macd_line, signal_line)]
    return MACDResult(macd_line, signal_line, hist)


@dataclass
class BollingerResult:
    upper: List[float]
    mid: List[float]
    lower: List[float]
    pct_b: List[float]


def bollinger(closes: Sequence[float], period: int = 20, mult: float = 2.0) -> BollingerResult:
    mid = sma(closes, period)
    sd = stdev(closes, period)
    upper, lower, pct_b = [], [], []
    for c, m, s in zip(closes, mid, sd):
        if m != m or s != s:
            upper.append(float("nan")); lower.append(float("nan")); pct_b.append(float("nan"))
            continue
        u, l = m + mult * s, m - mult * s
        upper.append(u); lower.append(l)
        pct_b.append((c - l) / (u - l) if u != l else 0.5)
    return BollingerResult(upper, mid, lower, pct_b)


def volume_zscore(volumes: Sequence[float], period: int = 20) -> List[float]:
    out: List[float] = []
    for i in range(len(volumes)):
        if i < period - 1:
            out.append(float("nan"))
            continue
        window = volumes[i - period + 1 : i + 1]
        m = sum(window) / period
        var = sum((x - m) ** 2 for x in window) / period
        sd = var ** 0.5
        out.append((volumes[i] - m) / sd if sd > 0 else 0.0)
    return out


def slope(values: Sequence[float], lookback: int = 5) -> float:
    if len(values) < lookback + 1:
        return 0.0
    tail = values[-(lookback + 1):]
    diffs = [tail[i + 1] - tail[i] for i in range(lookback)]
    avg = sum(diffs) / lookback
    base = abs(tail[-1]) if tail[-1] else 1.0
    return avg / base
