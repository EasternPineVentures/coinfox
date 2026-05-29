"""The churn daemon — coinfox's always-on brain.

Runs in the background. Every `interval_seconds`:
  1. Gathers fresh intel from all sources (in parallel).
  2. Builds a compact, structured digest.
  3. Asks FoxClaw to analyze it.
  4. Stores the resulting Thought in SQLite for later use by the dashboard,
     the model, and historical drift analysis.

This is the **system-facing** AI loop — no human prompts. It just churns,
so when you check in, the fox has already thought about it.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..intel import Intel, gather
from .base import AICall
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
"""


SYSTEM_PROMPT = """You are FoxClaw, the analytical brain of coinfox, a community
BTC-watching tool. Read the digest of current BTC intel and respond with STRICT JSON:

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
    return d


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
    ):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.interval = interval_seconds
        self.foxclaw = foxclaw or FoxClaw()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)

    def tick_once(self) -> Optional[Thought]:
        """One churn cycle. Returns the Thought stored, or None on failure."""
        try:
            intel = gather()
        except Exception:
            return None
        digest = _digest(intel)
        if not digest:
            return None
        prompt = "Current BTC intel digest:\n" + json.dumps(digest, indent=2)
        try:
            resp = self.foxclaw.quick(prompt, system=SYSTEM_PROMPT,
                                      max_tokens=350, temperature=0.3)
        except NoFreeProviderError:
            return None
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
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO thoughts "
                "(ts, bias, conviction, headline, body, provider, model, cost_tier, digest) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (t.ts, t.bias, t.conviction, t.headline, t.body,
                 t.provider, t.model, t.cost_tier, json.dumps(digest)),
            )
        return t

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
