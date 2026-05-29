"""Regime detection for pulse digests.

Designed for constant-time updates per tick:
- EWMA volatility for fast squeeze detection.
- Rolling linear-trend strength via running sums for O(1) updates.
- Panic/macro-shock hooks for future cross-symbol expansion.
"""

from __future__ import annotations

import math
import random
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Deque, Dict, List, Optional, Tuple


@dataclass
class RegimeConfig:
    window_size: int = 100
    vol_lookback: int = 20
    trend_strength_threshold: float = 0.60
    chop_threshold: float = 0.40
    panic_volume_mult: float = 2.0
    panic_price_drop_pct: float = 0.03
    squeeze_volatility_pct: float = 0.005
    macro_shock_panic_ratio: float = 0.70


@dataclass(frozen=True)
class RegimeTuneCase:
    label: str
    prices: List[float]
    volumes: List[float]
    panic_ratio_hint: Optional[float] = None


class RegimeDetector:
    """Online regime detector with O(1) amortized updates."""

    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()
        self.prices: Deque[float] = deque(maxlen=self.config.window_size)
        self.volumes: Deque[float] = deque(maxlen=self.config.window_size)
        self.timestamps: Deque[datetime] = deque(maxlen=self.config.window_size)
        self._vol_ewma: Optional[float] = None
        self._alpha = 2.0 / (self.config.vol_lookback + 1.0)

        # Running sums for rolling linear regression on price.
        self._sum_y = 0.0
        self._sum_yy = 0.0
        self._sum_xy = 0.0

    def update(self, price: float, volume: float, timestamp: Optional[datetime] = None) -> None:
        if price <= 0:
            return

        if timestamp is None:
            timestamp = datetime.utcnow()

        prev_price = self.prices[-1] if self.prices else None
        was_full = len(self.prices) == self.config.window_size
        y_old = self.prices[0] if was_full else 0.0

        old_sum_y = self._sum_y
        self.prices.append(float(price))
        self.volumes.append(float(volume) if math.isfinite(float(volume)) else 0.0)
        self.timestamps.append(timestamp)

        y_new = float(price)
        if was_full:
            n = self.config.window_size
            self._sum_y = old_sum_y - y_old + y_new
            self._sum_yy = self._sum_yy - y_old * y_old + y_new * y_new
            # Shift x indices left by one, then append new point at x=n-1.
            self._sum_xy = self._sum_xy - old_sum_y + y_old + (n - 1) * y_new
        else:
            n = len(self.prices)
            self._sum_y += y_new
            self._sum_yy += y_new * y_new
            self._sum_xy += (n - 1) * y_new

        if prev_price is not None and prev_price > 0:
            ret = math.log(y_new / prev_price)
            sq_ret = ret * ret
            if self._vol_ewma is None:
                self._vol_ewma = sq_ret
            else:
                self._vol_ewma = self._alpha * sq_ret + (1.0 - self._alpha) * self._vol_ewma

    def get_regime(self, panic_ratio_hint: Optional[float] = None) -> Tuple[str, float]:
        if len(self.prices) < max(6, self.config.vol_lookback):
            return "chop", 0.2

        if panic_ratio_hint is not None and panic_ratio_hint >= self.config.macro_shock_panic_ratio:
            conf = min(0.98, 0.50 + 0.50 * float(panic_ratio_hint))
            return "macro_shock", conf

        drop, spike = self._panic_metrics()
        if drop >= self.config.panic_price_drop_pct and spike >= self.config.panic_volume_mult:
            return "panic", min(0.95, 0.55 + drop * 8.0)

        strength = self._trend_strength()
        if strength >= self.config.trend_strength_threshold:
            return "trend", strength

        vol = math.sqrt(self._vol_ewma) if self._vol_ewma else 0.0
        if vol <= self.config.squeeze_volatility_pct:
            conf = 1.0 - min(1.0, vol / max(self.config.squeeze_volatility_pct, 1e-9))
            return "squeeze", max(0.35, conf)

        if strength <= self.config.chop_threshold:
            return "chop", 1.0 - strength
        return "chop", 0.5

    def metrics(self) -> Dict[str, float]:
        drop, spike = self._panic_metrics()
        return {
            "window_size": float(len(self.prices)),
            "ewma_vol": float(math.sqrt(self._vol_ewma) if self._vol_ewma else 0.0),
            "trend_strength": float(self._trend_strength()),
            "panic_drop_pct": float(drop * 100.0),
            "panic_volume_mult": float(spike),
        }

    def _panic_metrics(self) -> Tuple[float, float]:
        n = len(self.prices)
        if n < self.config.vol_lookback + 1:
            return 0.0, 1.0
        ref = self.prices[-self.config.vol_lookback]
        now = self.prices[-1]
        drop = max(0.0, (ref - now) / ref) if ref > 0 else 0.0

        vols = list(self.volumes)[-self.config.vol_lookback:]
        if len(vols) < 2:
            return drop, 1.0
        current = vols[-1]
        baseline = sum(vols[:-1]) / max(1, len(vols) - 1)
        spike = current / baseline if baseline > 0 else 1.0
        return drop, spike

    def _trend_strength(self) -> float:
        n = len(self.prices)
        if n < 3:
            return 0.0

        # Rebuild sums during the warmup period where the window length changes.
        if n < self.config.window_size:
            vals = list(self.prices)
            self._sum_y = sum(vals)
            self._sum_yy = sum(v * v for v in vals)
            self._sum_xy = sum(i * v for i, v in enumerate(vals))

        sum_x = n * (n - 1) / 2.0
        sum_x2 = (n - 1) * n * (2 * n - 1) / 6.0

        sxy = n * self._sum_xy - sum_x * self._sum_y
        sxx = n * sum_x2 - sum_x * sum_x
        syy = n * self._sum_yy - self._sum_y * self._sum_y
        if sxx <= 1e-12 or syy <= 1e-12:
            return 0.0

        r = sxy / math.sqrt(sxx * syy)
        r2 = max(0.0, min(1.0, r * r))
        return r2


def run_regime_benchmark(
    symbols: int = 100,
    updates_per_symbol: int = 500,
    window_size: int = 100,
    seed: int = 7,
) -> dict:
    """Synthetic stress benchmark for detector update/classification throughput."""
    symbols = max(1, int(symbols))
    updates_per_symbol = max(1, int(updates_per_symbol))
    cfg = RegimeConfig(window_size=max(20, int(window_size)))
    rng = random.Random(seed)

    detectors: List[RegimeDetector] = [RegimeDetector(cfg) for _ in range(symbols)]
    prices = [50000.0 + i * 10.0 for i in range(symbols)]
    start = time.perf_counter()

    for step in range(updates_per_symbol):
        ts = datetime.utcnow()
        for i, det in enumerate(detectors):
            shock = 0.0
            if step % 200 == 0 and i % 13 == 0:
                shock = -0.02
            drift = 0.0002 * math.sin((i + 1) * 0.03)
            noise = rng.uniform(-0.0025, 0.0025)
            ret = drift + noise + shock
            prices[i] = max(10.0, prices[i] * (1.0 + ret))
            volume = 1000.0 * (1.0 + abs(ret) * 30.0 + rng.uniform(0.0, 0.3))
            det.update(prices[i], volume, ts)
            det.get_regime()

    elapsed = time.perf_counter() - start
    total_updates = symbols * updates_per_symbol
    updates_per_sec = total_updates / elapsed if elapsed > 0 else 0.0
    us_per_update = (elapsed * 1_000_000.0 / total_updates) if total_updates > 0 else 0.0

    sample_metrics = detectors[0].metrics() if detectors else {}
    sample_regime = detectors[0].get_regime()[0] if detectors else "chop"
    return {
        "symbols": symbols,
        "updates_per_symbol": updates_per_symbol,
        "total_updates": total_updates,
        "elapsed_s": round(elapsed, 4),
        "updates_per_s": round(updates_per_sec, 2),
        "us_per_update": round(us_per_update, 2),
        "sample_regime": sample_regime,
        "sample_metrics": sample_metrics,
        "window_size": cfg.window_size,
    }


def score_regime_config(
    config: Optional[RegimeConfig] = None,
    cases: Optional[List[RegimeTuneCase]] = None,
) -> dict:
    """Score a detector config against deterministic labeled scenarios."""
    cfg = config or RegimeConfig()
    suite = cases or synthetic_regime_cases()
    labels = ["trend", "chop", "panic", "squeeze", "macro_shock"]
    confusion = {label: {pred: 0 for pred in labels} for label in labels}
    correct = 0
    confidence_total = 0.0

    for case in suite:
        det = RegimeDetector(cfg)
        start_ts = datetime(2026, 1, 1)
        for i, price in enumerate(case.prices):
            volume = case.volumes[i] if i < len(case.volumes) else 0.0
            det.update(price, volume, start_ts + timedelta(minutes=i))
        pred, confidence = det.get_regime(panic_ratio_hint=case.panic_ratio_hint)
        label = case.label if case.label in confusion else "chop"
        if pred not in confusion[label]:
            for row in confusion.values():
                row[pred] = 0
        confusion[label][pred] = confusion[label].get(pred, 0) + 1
        correct += 1 if pred == label else 0
        confidence_total += float(confidence)

    sample_size = len(suite)
    accuracy = correct / sample_size if sample_size else 0.0
    return {
        "sample_size": sample_size,
        "accuracy": round(accuracy, 4),
        "mean_confidence": round(confidence_total / sample_size, 4) if sample_size else 0.0,
        "confusion": confusion,
        "config": _config_dict(cfg),
    }


def tune_regime_thresholds(seed: int = 13) -> dict:
    """Grid-search lightweight detector thresholds on deterministic cases."""
    cases = synthetic_regime_cases(seed=seed)
    baseline_cfg = RegimeConfig()
    baseline = score_regime_config(baseline_cfg, cases)
    best_cfg = baseline_cfg
    best = baseline

    for trend_threshold in (0.45, 0.55, 0.60, 0.70, 0.80):
        for chop_threshold in (0.25, 0.35, 0.40, 0.50):
            for panic_drop in (0.02, 0.03, 0.04):
                for panic_volume in (1.5, 2.0, 2.5):
                    for squeeze_vol in (0.003, 0.005, 0.008):
                        if chop_threshold >= trend_threshold:
                            continue
                        cfg = RegimeConfig(
                            trend_strength_threshold=trend_threshold,
                            chop_threshold=chop_threshold,
                            panic_price_drop_pct=panic_drop,
                            panic_volume_mult=panic_volume,
                            squeeze_volatility_pct=squeeze_vol,
                        )
                        score = score_regime_config(cfg, cases)
                        key = (score["accuracy"], score["mean_confidence"])
                        best_key = (best["accuracy"], best["mean_confidence"])
                        if key > best_key:
                            best_cfg = cfg
                            best = score

    return {
        "baseline": baseline,
        "best": best,
        "improved": (
            best["accuracy"] > baseline["accuracy"]
            or best["mean_confidence"] > baseline["mean_confidence"]
        ),
        "recommended_config": _config_dict(best_cfg),
    }


def synthetic_regime_cases(seed: int = 13) -> List[RegimeTuneCase]:
    """Build labeled, deterministic scenarios for fast threshold tuning."""
    rng = random.Random(seed)
    cases: List[RegimeTuneCase] = []

    for direction in (1.0, -1.0):
        for drift in (0.0012, 0.0018, 0.0024):
            price = 100.0
            prices = []
            volumes = []
            for i in range(120):
                price *= 1.0 + direction * drift + rng.uniform(-0.00025, 0.00025)
                prices.append(price)
                volumes.append(1000.0 + i * 2.0)
            cases.append(RegimeTuneCase("trend", prices, volumes))

    for amp in (0.6, 1.1, 1.6):
        prices = []
        volumes = []
        for i in range(120):
            price = 100.0 + math.sin(i * 0.55) * amp + math.sin(i * 1.7) * (amp * 0.15)
            prices.append(max(1.0, price))
            volumes.append(1000.0 + (i % 7) * 45.0)
        cases.append(RegimeTuneCase("chop", prices, volumes))

    for drop_step in (0.011, 0.014, 0.017):
        price = 100.0
        prices = []
        volumes = []
        for i in range(32):
            price *= 1.0 + rng.uniform(-0.0002, 0.0002)
            prices.append(price)
            volumes.append(1000.0)
        for i in range(5):
            price *= 1.0 - drop_step
            prices.append(price)
            volumes.append(1700.0 if i < 4 else 4300.0)
        cases.append(RegimeTuneCase("panic", prices, volumes))

    for amp in (0.002, 0.004, 0.006):
        prices = []
        volumes = []
        for i in range(80):
            price = 100.0 * (1.0 + amp * math.sin(i * 0.7))
            prices.append(price)
            volumes.append(900.0 + math.sin(i) * 12.0)
        cases.append(RegimeTuneCase("squeeze", prices, volumes))

    macro_prices = [100.0 + i * 0.02 for i in range(50)]
    macro_volumes = [1000.0 for _ in macro_prices]
    cases.append(RegimeTuneCase("macro_shock", macro_prices, macro_volumes, panic_ratio_hint=0.8))
    return cases


def _config_dict(cfg: RegimeConfig) -> dict:
    return {
        "window_size": cfg.window_size,
        "vol_lookback": cfg.vol_lookback,
        "trend_strength_threshold": cfg.trend_strength_threshold,
        "chop_threshold": cfg.chop_threshold,
        "panic_volume_mult": cfg.panic_volume_mult,
        "panic_price_drop_pct": cfg.panic_price_drop_pct,
        "squeeze_volatility_pct": cfg.squeeze_volatility_pct,
        "macro_shock_panic_ratio": cfg.macro_shock_panic_ratio,
    }
