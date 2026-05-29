"""The pulse daemon — coinfox's always-on brain.

Runs in the background. Every `interval_seconds`:
  1. Gathers fresh intel from all sources (in parallel).
  2. Builds a compact, structured digest.
  3. Asks FoxClaw to analyze it.
  4. Stores the resulting Thought in SQLite for later use by the dashboard,
     the model, and historical drift analysis.

This is the **system-facing** AI loop — no human prompts. It keeps a steady
market pulse, so when you check in, the fox has already thought about it.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, List, Optional, Tuple

from ..intel import Intel, gather
from .base import AICall
from .regime import RegimeDetector
from .router import FoxClaw, NoFreeProviderError


@dataclass
class Thought:
    ts: int                        # unix seconds
    bias: str                      # "long" | "short" | "neutral" — extracted by AI
    conviction: int                # 1..5
    headline: str                  # one-sentence take
    body: str                      # multi-sentence reasoning
    provider: str
    model: str
    cost_tier: str
    digest_keys: List[str] = field(default_factory=list)


SCHEMA = """
CREATE TABLE IF NOT EXISTS thoughts (
    ts          INTEGER PRIMARY KEY,
    bias        TEXT NOT NULL,
    conviction  INTEGER NOT NULL,
    headline    TEXT NOT NULL,
    body        TEXT NOT NULL,
    provider    TEXT NOT NULL,
    model       TEXT NOT NULL,
    cost_tier   TEXT NOT NULL,
    digest      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_thoughts_ts ON thoughts(ts DESC);
CREATE TABLE IF NOT EXISTS churn_state (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_ts  INTEGER NOT NULL
);
"""


SYSTEM_PROMPT = """You are FoxClaw, the internal analytical context layer for CoinFox,
a public market intelligence tool from Eastern Pine Intelligence. Read the digest
of current market intel and respond with STRICT JSON:

{
  "bias": "long" | "short" | "neutral",
  "conviction": 1-5,
  "headline": "one short sentence, plain English, no hype",
  "body": "2-4 sentences explaining the read, citing the strongest data points"
}

Rules:
- Cite specific numbers from the digest where possible.
- Be calibrated. Conviction 5 only if multiple independent signals strongly agree.
- Never recommend specific trades. This is analysis, not advice.
- Respond with ONLY the JSON object, no markdown fences, no preamble."""


NUMERIC_FEATURE_KEYS = [
    "price_median_usd",
    "price_spread_pct",
    "btc_dominance_pct",
    "total_volume_usd",
    "avg_funding_pct_8h",
    "perp_basis_pct",
    "fee_fast_sat_vb",
    "mempool_tx",
    "hashrate_ehs",
    "blocks_to_halving",
    "fng_now",
    "fng_delta_1d",
    "source_error_count",
]

SOURCE_KEYS = [
    "prices",
    "global_market",
    "derivatives",
    "onchain",
    "news",
    "social",
    "dev",
    "macro",
    "sentiment",
]


def _digest(intel: Intel) -> dict:
    """Compress the intel bundle into a small dict the model can chew on."""
    d: dict = {}
    if intel.prices and intel.prices.median_usd is not None:
        d["price_median_usd"] = round(intel.prices.median_usd, 2)
        d["price_spread_pct"] = round(intel.prices.spread_pct or 0.0, 4)
        d["venues"] = [q.exchange for q in intel.prices.quotes]
    if intel.global_market:
        g = intel.global_market
        d["btc_dominance_pct"] = round(g["btc_dominance_pct"], 2)
        d["total_volume_usd"] = g["total_volume_usd"]
    if intel.derivatives:
        if intel.derivatives.avg_funding is not None:
            d["avg_funding_pct_8h"] = round(intel.derivatives.avg_funding * 100, 5)
        if intel.derivatives.basis_pct is not None:
            d["perp_basis_pct"] = round(intel.derivatives.basis_pct, 4)
        d["oi_venues"] = [oi.venue for oi in intel.derivatives.open_interest]
    if intel.onchain:
        o = intel.onchain
        d["fee_fast_sat_vb"] = o.fee_fast_sat_vb
        d["mempool_tx"] = o.mempool_count
        d["hashrate_ehs"] = o.hashrate_ehs
        d["blocks_to_halving"] = o.blocks_to_halving
    if intel.sentiment and intel.sentiment.fng_now:
        d["fng_now"] = intel.sentiment.fng_now.value
        d["fng_class"] = intel.sentiment.fng_now.classification
        if intel.sentiment.fng_yesterday:
            d["fng_delta_1d"] = intel.sentiment.fng_now.value - intel.sentiment.fng_yesterday.value
    if intel.macro and intel.macro.series:
        d["macro_changes_pct"] = {k: round(v, 3) for k, v in intel.macro.changes_pct.items()}
    if intel.news and intel.news.headlines:
        d["recent_headlines"] = [h.title for h in intel.news.headlines[:8]]
    if intel.social and intel.social.top_posts:
        d["reddit_top"] = [{"title": p.title, "score": p.score}
                           for p in intel.social.top_posts[:5]]
    source_status = {}
    for source in SOURCE_KEYS:
        if source in intel.errors:
            source_status[source] = "error"
        elif getattr(intel, source, None) is None:
            source_status[source] = "missing"
        else:
            source_status[source] = "ok"

    d["source_status"] = source_status
    d["source_ok_count"] = sum(1 for status in source_status.values() if status == "ok")
    d["source_error_count"] = len(intel.errors)
    if intel.errors:
        d["source_error_names"] = sorted(intel.errors.keys())[:8]
    return d


def _source_reliability_snapshot(conn: sqlite3.Connection, digest: dict, lookback: int = 300) -> dict:
    """Compute rolling per-source reliability using Laplace-smoothed success rates."""
    current = digest.get("source_status")
    if not isinstance(current, dict):
        return {
            "sample_size": 0,
            "overall": 0.0,
            "weakest_source": None,
            "per_source": {},
        }

    rows = conn.execute(
        "SELECT digest FROM thoughts ORDER BY ts DESC LIMIT ?",
        (lookback,),
    ).fetchall()

    ok_counts = {key: 0 for key in SOURCE_KEYS}
    fail_counts = {key: 0 for key in SOURCE_KEYS}
    sample_size = 0

    for row in rows:
        try:
            old = json.loads(row[0])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        statuses = old.get("source_status")
        if not isinstance(statuses, dict):
            continue
        sample_size += 1
        for source in SOURCE_KEYS:
            status = str(statuses.get(source, "missing")).lower()
            if status == "ok":
                ok_counts[source] += 1
            else:
                fail_counts[source] += 1

    per_source: Dict[str, float] = {}
    for source in SOURCE_KEYS:
        ok = ok_counts[source]
        fail = fail_counts[source]
        per_source[source] = round((ok + 1.0) / (ok + fail + 2.0), 4)

    if not per_source:
        return {
            "sample_size": sample_size,
            "overall": 0.0,
            "weakest_source": None,
            "per_source": {},
        }

    weakest_source = min(per_source.items(), key=lambda kv: kv[1])[0]
    overall = round(mean(per_source.values()), 4)
    return {
        "sample_size": sample_size,
        "overall": overall,
        "weakest_source": weakest_source,
        "current_errors": [
            source for source, status in current.items()
            if str(status).lower() == "error"
        ],
        "per_source": per_source,
    }


def _extract_numeric_features(digest: dict) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key in NUMERIC_FEATURE_KEYS:
        v = digest.get(key)
        if isinstance(v, (int, float)) and math.isfinite(float(v)):
            out[key] = float(v)

    macro = digest.get("macro_changes_pct")
    if isinstance(macro, dict) and macro:
        vals = [float(v) for v in macro.values() if isinstance(v, (int, float))]
        if vals:
            out["macro_abs_mean_pct"] = mean(abs(v) for v in vals)
            out["macro_abs_max_pct"] = max(abs(v) for v in vals)
    return out


def _learning_snapshot(conn: sqlite3.Connection, digest: dict, lookback: int = 300) -> dict:
    """Rolling unsupervised anomaly score over historical digest features."""
    current = _extract_numeric_features(digest)
    if not current:
        return {
            "sample_size": 0,
            "anomaly_score": 0.0,
            "strange_market": False,
            "top_feature": None,
        }

    rows = conn.execute(
        "SELECT digest FROM thoughts ORDER BY ts DESC LIMIT ?",
        (lookback,),
    ).fetchall()
    history: Dict[str, List[float]] = {}
    for row in rows:
        try:
            old = json.loads(row[0])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        feats = _extract_numeric_features(old)
        for k, v in feats.items():
            history.setdefault(k, []).append(v)

    z_by_key: Dict[str, float] = {}
    for key, cur in current.items():
        vals = history.get(key, [])
        if len(vals) < 20:
            continue
        std = pstdev(vals)
        if std <= 1e-12:
            continue
        mu = mean(vals)
        z_by_key[key] = abs((cur - mu) / std)

    if not z_by_key:
        return {
            "sample_size": max((len(v) for v in history.values()), default=0),
            "anomaly_score": 0.0,
            "strange_market": False,
            "top_feature": None,
        }

    top_feature, top_z = max(z_by_key.items(), key=lambda kv: kv[1])
    mean_z = mean(z_by_key.values())
    score = max(top_z, mean_z)
    strange = score >= 2.5
    return {
        "sample_size": max((len(v) for v in history.values()), default=0),
        "anomaly_score": round(score, 3),
        "mean_z": round(mean_z, 3),
        "top_feature": top_feature,
        "top_feature_z": round(top_z, 3),
        "feature_count": len(z_by_key),
        "strange_market": strange,
    }


def _merge_intel(primary: Intel, secondary: Intel) -> Tuple[Intel, bool]:
    """Merge two snapshots and keep values from the first successful fetch."""
    merged = Intel(
        prices=primary.prices or secondary.prices,
        global_market=primary.global_market or secondary.global_market,
        derivatives=primary.derivatives or secondary.derivatives,
        onchain=primary.onchain or secondary.onchain,
        news=primary.news or secondary.news,
        social=primary.social or secondary.social,
        dev=primary.dev or secondary.dev,
        macro=primary.macro or secondary.macro,
        sentiment=primary.sentiment or secondary.sentiment,
        errors=dict(primary.errors),
    )

    for name in list(merged.errors.keys()):
        if getattr(merged, name, None) is not None:
            merged.errors.pop(name, None)
        elif name in secondary.errors:
            merged.errors[name] = secondary.errors[name]

    repaired = len(merged.errors) < len(primary.errors)
    return merged, repaired


def _fallback_thought(digest: dict, reason: str) -> Thought:
    learning = digest.get("learning") or {}
    strange = bool(learning.get("strange_market", False))
    score = learning.get("anomaly_score", 0.0)
    top_feature = learning.get("top_feature") or "n/a"
    src_err = int(digest.get("source_error_count", 0) or 0)

    headline = (
        "Degraded mode: data monitor active, waiting for AI provider"
        if not strange
        else "Degraded mode: market anomaly flagged while AI provider unavailable"
    )
    body = (
        "FoxClaw provider routing is temporarily unavailable, so coinfox switched to "
        "self-healing degraded mode and kept monitoring live inputs. "
        f"Anomaly score={score}, top feature={top_feature}, source errors={src_err}. "
        f"Reason: {reason}."
    )
    return Thought(
        ts=int(time.time()),
        bias="neutral",
        conviction=2 if not strange else 3,
        headline=headline,
        body=body[:2000],
        provider="system-fallback",
        model="rules-v1",
        cost_tier="local",
        digest_keys=sorted(digest.keys()),
    )


def _conviction_prob(conviction: int) -> float:
    mapping = {1: 0.52, 2: 0.57, 3: 0.63, 4: 0.70, 5: 0.78}
    return mapping.get(int(conviction), 0.60)


def _truth_label(ret_pct: float, neutral_band_pct: float = 0.20) -> str:
    if ret_pct > neutral_band_pct:
        return "long"
    if ret_pct < -neutral_band_pct:
        return "short"
    return "neutral"


def _parse_response(text: str) -> Optional[dict]:
    """Extract the JSON object even if the model added stray text."""
    text = text.strip()
    # Find first { and last }
    a = text.find("{")
    b = text.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        return json.loads(text[a:b + 1])
    except json.JSONDecodeError:
        return None


class ChurnDaemon:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        interval_seconds: int = 300,
        foxclaw: Optional[FoxClaw] = None,
        regime_detector: Optional[RegimeDetector] = None,
    ):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.interval = interval_seconds
        self.foxclaw = foxclaw or FoxClaw()
        self.regime = regime_detector or RegimeDetector()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)

    def _set_state(self, key: str, value: str) -> None:
        now = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO churn_state (key, value, updated_ts) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_ts=excluded.updated_ts",
                (key, value, now),
            )

    def _get_state(self, key: str) -> Optional[Tuple[str, int]]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value, updated_ts FROM churn_state WHERE key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        return str(row[0]), int(row[1])

    def health(self, stale_after_s: int = 900) -> dict:
        now = int(time.time())
        hb = self._get_state("heartbeat")
        phase = self._get_state("phase")
        last_ok = self._get_state("last_ok_ts")
        last_err = self._get_state("last_error")

        heartbeat_age = None
        if hb:
            heartbeat_age = max(0, now - hb[1])
        return {
            "phase": phase[0] if phase else "unknown",
            "heartbeat_age_s": heartbeat_age,
            "stale": bool(heartbeat_age is None or heartbeat_age > stale_after_s),
            "last_ok_age_s": (max(0, now - last_ok[1]) if last_ok else None),
            "last_error": (last_err[0] if last_err else None),
        }

    def tick_once(self) -> Optional[Thought]:
        """One pulse cycle. Returns the Thought stored, or None on failure."""
        self._set_state("phase", "gather")
        self._set_state("heartbeat", "tick-start")
        try:
            intel = gather()
        except Exception:
            self._set_state("last_error", "gather-failed")
            self._set_state("phase", "error")
            return None

        healed = False
        if len(intel.errors) >= 2:
            try:
                # Self-heal once for transient upstream/API hiccups.
                time.sleep(0.8)
                retry = gather()
                intel, healed = _merge_intel(intel, retry)
            except Exception:
                pass

        digest = _digest(intel)
        if not digest:
            return None
        digest["self_heal_applied"] = healed

        price = digest.get("price_median_usd")
        volume = digest.get("total_volume_usd")
        if isinstance(price, (int, float)) and price > 0:
            self.regime.update(float(price), float(volume) if isinstance(volume, (int, float)) else 0.0)
            regime_name, regime_conf = self.regime.get_regime()
            digest["regime"] = {
                "name": regime_name,
                "confidence": round(float(regime_conf), 4),
                "metrics": self.regime.metrics(),
            }

        with sqlite3.connect(self.db_path) as conn:
            digest["learning"] = _learning_snapshot(conn, digest)
            digest["source_reliability"] = _source_reliability_snapshot(conn, digest)

        self._set_state("phase", "llm")
        self._set_state("heartbeat", "llm")
        prompt = "Current BTC intel digest:\n" + json.dumps(digest, indent=2)
        try:
            resp = self.foxclaw.quick(prompt, system=SYSTEM_PROMPT,
                                      max_tokens=350, temperature=0.3)
        except NoFreeProviderError as e:
            t = _fallback_thought(digest, str(e))
            self._store_thought(t, digest)
            self._set_state("last_error", "no-provider-fallback")
            self._set_state("last_ok_ts", str(int(time.time())))
            self._set_state("phase", "idle")
            self._set_state("heartbeat", "stored-fallback")
            return t
        parsed = _parse_response(resp.text) or {}
        bias = str(parsed.get("bias", "neutral")).lower()
        if bias not in ("long", "short", "neutral"):
            bias = "neutral"
        try:
            conviction = int(parsed.get("conviction", 1))
        except (TypeError, ValueError):
            conviction = 1
        conviction = max(1, min(5, conviction))
        headline = str(parsed.get("headline", "")).strip()[:240] or "no headline"
        body = str(parsed.get("body", resp.text)).strip()[:2000]
        t = Thought(
            ts=int(time.time()),
            bias=bias,
            conviction=conviction,
            headline=headline,
            body=body,
            provider=resp.provider_used,
            model=resp.model_used,
            cost_tier=resp.cost_tier,
            digest_keys=sorted(digest.keys()),
        )
        self._store_thought(t, digest)
        self._set_state("last_error", "")
        self._set_state("last_ok_ts", str(int(time.time())))
        self._set_state("phase", "idle")
        self._set_state("heartbeat", "stored")
        return t

    def _store_thought(self, thought: Thought, digest: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO thoughts "
                "(ts, bias, conviction, headline, body, provider, model, cost_tier, digest) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (thought.ts, thought.bias, thought.conviction, thought.headline, thought.body,
                 thought.provider, thought.model, thought.cost_tier, json.dumps(digest)),
            )

    def latest(self) -> Optional[Thought]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT ts, bias, conviction, headline, body, provider, model, cost_tier "
                "FROM thoughts ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return Thought(*row, digest_keys=[])

    def recent(self, limit: int = 10) -> List[Thought]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT ts, bias, conviction, headline, body, provider, model, cost_tier "
                "FROM thoughts ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Thought(*r, digest_keys=[]) for r in rows]

    def latest_digest(self) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT digest FROM thoughts ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def accuracy_report(self, window: int = 200, horizon_steps: int = 6,
                        neutral_band_pct: float = 0.20) -> dict:
        """Evaluate directional accuracy from stored thought history.

        horizon_steps is measured in pulse cycles, not fixed minutes.
        """
        if horizon_steps < 1:
            horizon_steps = 1

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT ts, bias, conviction, digest FROM thoughts "
                "ORDER BY ts DESC LIMIT ?",
                (max(window + horizon_steps + 2, 50),),
            ).fetchall()

        if len(rows) <= horizon_steps + 5:
            return {
                "sample_size": 0,
                "horizon_steps": horizon_steps,
                "hit_rate": 0.0,
                "weighted_hit_rate": 0.0,
                "brier_like": 0.0,
                "strange_rate": 0.0,
            }

        rows = list(reversed(rows))
        eval_count = min(window, len(rows) - horizon_steps)
        hits = 0
        weighted_hits = 0.0
        total_w = 0.0
        brier_terms = []
        strange_count = 0

        used = 0
        for i in range(eval_count):
            now = rows[i]
            fut = rows[i + horizon_steps]
            bias = str(now[1]).lower()
            conviction = int(now[2])
            try:
                now_d = json.loads(now[3])
                fut_d = json.loads(fut[3])
            except (TypeError, ValueError, json.JSONDecodeError):
                continue

            p0 = now_d.get("price_median_usd")
            p1 = fut_d.get("price_median_usd")
            if not isinstance(p0, (int, float)) or not isinstance(p1, (int, float)) or p0 <= 0:
                continue

            ret_pct = (float(p1) - float(p0)) / float(p0) * 100.0
            truth = _truth_label(ret_pct, neutral_band_pct=neutral_band_pct)
            hit = bias == truth
            w = max(1.0, float(conviction))

            used += 1
            hits += 1 if hit else 0
            weighted_hits += w if hit else 0.0
            total_w += w

            p = _conviction_prob(conviction)
            if bias == "long":
                outcome = 1.0 if truth == "long" else 0.0
            elif bias == "short":
                outcome = 1.0 if truth == "short" else 0.0
            else:
                # For neutral calls, score probability of "non-directional" outcome.
                outcome = 1.0 if truth == "neutral" else 0.0
            brier_terms.append((p - outcome) ** 2)

            learning = now_d.get("learning") if isinstance(now_d, dict) else None
            if isinstance(learning, dict) and learning.get("strange_market"):
                strange_count += 1

        if used == 0:
            return {
                "sample_size": 0,
                "horizon_steps": horizon_steps,
                "hit_rate": 0.0,
                "weighted_hit_rate": 0.0,
                "brier_like": 0.0,
                "strange_rate": 0.0,
            }

        return {
            "sample_size": used,
            "horizon_steps": horizon_steps,
            "hit_rate": round(hits / used, 4),
            "weighted_hit_rate": round(weighted_hits / total_w, 4) if total_w > 0 else 0.0,
            "brier_like": round(mean(brier_terms), 4) if brier_terms else 0.0,
            "strange_rate": round(strange_count / used, 4),
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="coinfox-churn")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick_once()
            except Exception:
                pass
            # responsive sleep
            for _ in range(self.interval):
                if self._stop.is_set():
                    return
                time.sleep(1)


def _default_db_path() -> Path:
    base = Path.home() / ".coinfox"
    return base / "churn.sqlite"
