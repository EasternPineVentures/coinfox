"""Replay and quality gates for pulse thought history."""

from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class ReplayThought:
    ts: int
    bias: str
    conviction: int
    digest: dict


def _conviction_prob(conviction: int) -> float:
    mapping = {1: 0.52, 2: 0.57, 3: 0.63, 4: 0.70, 5: 0.78}
    return mapping.get(int(conviction), 0.60)


def _truth_label(ret_pct: float, neutral_band_pct: float = 0.20) -> str:
    if ret_pct > neutral_band_pct:
        return "long"
    if ret_pct < -neutral_band_pct:
        return "short"
    return "neutral"


def load_replay_thoughts(db_path: Path, limit: int = 500) -> List[ReplayThought]:
    """Load replayable thoughts from the pulse SQLite database."""
    rows: List[ReplayThought] = []
    path = Path(db_path)
    if not path.exists():
        return rows
    try:
        with closing(sqlite3.connect(path)) as conn:
            data = conn.execute(
                "SELECT ts, bias, conviction, digest FROM thoughts ORDER BY ts DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
    except sqlite3.OperationalError:
        return rows

    for ts, bias, conviction, digest_raw in data:
        try:
            digest = json.loads(digest_raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(digest, dict):
            rows.append(
                ReplayThought(
                    ts=int(ts),
                    bias=str(bias).lower(),
                    conviction=max(1, min(5, int(conviction))),
                    digest=digest,
                )
            )
    return sorted(rows, key=lambda thought: thought.ts)


def evaluate_replay(
    thoughts: Iterable[ReplayThought],
    horizon_steps: int = 6,
    neutral_band_pct: float = 0.20,
    max_samples: Optional[int] = None,
) -> dict:
    """Score stored thoughts against future price movement."""
    rows = sorted(list(thoughts), key=lambda thought: thought.ts)
    horizon = max(1, int(horizon_steps))
    if len(rows) <= horizon:
        return _empty_report(horizon)

    eval_count = len(rows) - horizon
    if max_samples is not None:
        eval_count = min(eval_count, max(1, int(max_samples)))

    hits = 0
    weighted_hits = 0.0
    total_w = 0.0
    brier_terms: List[float] = []
    strange_count = 0
    label_counts = {"long": 0, "short": 0, "neutral": 0}
    truth_counts = {"long": 0, "short": 0, "neutral": 0}
    used = 0

    for i in range(eval_count):
        now = rows[i]
        fut = rows[i + horizon]
        p0 = now.digest.get("price_median_usd")
        p1 = fut.digest.get("price_median_usd")
        if not isinstance(p0, (int, float)) or not isinstance(p1, (int, float)):
            continue
        if p0 <= 0 or not math.isfinite(float(p0)) or not math.isfinite(float(p1)):
            continue

        ret_pct = (float(p1) - float(p0)) / float(p0) * 100.0
        truth = _truth_label(ret_pct, neutral_band_pct=neutral_band_pct)
        bias = now.bias if now.bias in label_counts else "neutral"
        conviction = max(1, min(5, int(now.conviction)))
        hit = bias == truth
        weight = max(1.0, float(conviction))

        used += 1
        hits += 1 if hit else 0
        weighted_hits += weight if hit else 0.0
        total_w += weight
        label_counts[bias] += 1
        truth_counts[truth] += 1

        prob = _conviction_prob(conviction)
        if bias == "long":
            outcome = 1.0 if truth == "long" else 0.0
        elif bias == "short":
            outcome = 1.0 if truth == "short" else 0.0
        else:
            outcome = 1.0 if truth == "neutral" else 0.0
        brier_terms.append((prob - outcome) ** 2)

        learning = now.digest.get("learning")
        if isinstance(learning, dict) and learning.get("strange_market"):
            strange_count += 1

    if used == 0:
        return _empty_report(horizon)

    return {
        "sample_size": used,
        "horizon_steps": horizon,
        "hit_rate": round(hits / used, 4),
        "weighted_hit_rate": round(weighted_hits / total_w, 4) if total_w > 0 else 0.0,
        "brier_like": round(mean(brier_terms), 4) if brier_terms else 0.0,
        "strange_rate": round(strange_count / used, 4),
        "label_counts": label_counts,
        "truth_counts": truth_counts,
        "start_ts": rows[0].ts,
        "end_ts": rows[min(len(rows) - 1, eval_count + horizon - 1)].ts,
    }


def quality_gate(
    report: dict,
    min_sample_size: int = 30,
    min_hit_rate: float = 0.55,
    max_brier_like: float = 0.35,
) -> dict:
    """Convert a replay report into pass/fail gate details."""
    checks = {
        "sample_size": int(report.get("sample_size", 0)) >= int(min_sample_size),
        "hit_rate": float(report.get("hit_rate", 0.0)) >= float(min_hit_rate),
        "brier_like": float(report.get("brier_like", 1.0)) <= float(max_brier_like),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "thresholds": {
            "min_sample_size": int(min_sample_size),
            "min_hit_rate": float(min_hit_rate),
            "max_brier_like": float(max_brier_like),
        },
        "report": report,
    }


def run_replay_quality_gate(
    db_path: Optional[Path] = None,
    synthetic: bool = False,
    window: int = 500,
    horizon_steps: int = 6,
    neutral_band_pct: float = 0.20,
    min_sample_size: int = 30,
    min_hit_rate: float = 0.55,
    max_brier_like: float = 0.35,
) -> dict:
    """Run the replay report and quality gate in one call."""
    if synthetic:
        thoughts = synthetic_replay_thoughts()
    else:
        if db_path is None:
            db_path = Path.home() / ".coinfox" / "churn.sqlite"
        thoughts = load_replay_thoughts(Path(db_path), limit=max(1, int(window)))

    report = evaluate_replay(
        thoughts,
        horizon_steps=max(1, int(horizon_steps)),
        neutral_band_pct=float(neutral_band_pct),
        max_samples=max(1, int(window)),
    )
    out = quality_gate(
        report,
        min_sample_size=max(1, int(min_sample_size)),
        min_hit_rate=float(min_hit_rate),
        max_brier_like=float(max_brier_like),
    )
    out["source"] = "synthetic" if synthetic else str(db_path)
    return out


def synthetic_replay_thoughts() -> List[ReplayThought]:
    """Deterministic fixture with trend, neutral, and downtrend segments."""
    thoughts: List[ReplayThought] = []
    ts = 1_800_000_000
    price = 100.0

    for i in range(24):
        price *= 1.004
        thoughts.append(_synthetic_thought(ts + i * 60, price, "long", 4))

    base = price
    for i in range(24):
        wobble = 1.0 + 0.0003 * math.sin(i)
        thoughts.append(_synthetic_thought(ts + (24 + i) * 60, base * wobble, "neutral", 3))

    price = base
    for i in range(24):
        price *= 0.996
        thoughts.append(_synthetic_thought(ts + (48 + i) * 60, price, "short", 4))

    return thoughts


def _synthetic_thought(ts: int, price: float, bias: str, conviction: int) -> ReplayThought:
    return ReplayThought(
        ts=ts,
        bias=bias,
        conviction=conviction,
        digest={
            "price_median_usd": round(float(price), 4),
            "learning": {"strange_market": False},
        },
    )


def _empty_report(horizon_steps: int) -> dict:
    return {
        "sample_size": 0,
        "horizon_steps": max(1, int(horizon_steps)),
        "hit_rate": 0.0,
        "weighted_hit_rate": 0.0,
        "brier_like": 0.0,
        "strange_rate": 0.0,
        "label_counts": {"long": 0, "short": 0, "neutral": 0},
        "truth_counts": {"long": 0, "short": 0, "neutral": 0},
    }
