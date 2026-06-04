# CoinFox Perfection Rollout (Free-First)

CoinFox is the public market intelligence product from Eastern Pine Intelligence,
the open-source technical lab from Eastern Pine Ventures.

This plan aims for continuously improving reliability and calibration under real market conditions.
Absolute accuracy at all times is not physically achievable in open markets, so the standard is:

- Detect regime shifts fast.
- Fail gracefully when dependencies break.
- Measure prediction quality continuously.
- Improve only when metrics prove it.

## North Star Metrics

- Directional hit rate (rolling, horizon-adjusted)
- Confidence-weighted hit rate
- Brier-like calibration score
- Strange-market detection precision/recall (event review)
- Source uptime and self-heal recovery rate
- Mean time to recover from provider/source failure

## Phase 1: Reliability Core (Implemented in this pass)

Status: done

- Always-on AI loop with real-time status panel:
  - `python -m coinfox pulse run --interval 300`
- Self-healing cycle:
  - Auto-retry when multiple source fetches fail
  - Merge partial snapshots to recover data coverage
- Degraded fallback thought mode:
  - If no AI provider answers, CoinFox still emits an explainable thought
- Learning snapshot (rolling anomaly detection):
  - Z-score based anomaly scoring from historical digests
  - `strange_market` flag + top anomalous feature
- Online quality telemetry:
  - `python -m coinfox pulse metrics --window 200 --horizon-steps 6`

## Phase 2: Data Integrity + Trust Layer

Status: next

- Add per-source quality weights (freshness, latency, failure streak)
- Add staleness gates: reject stale feeds from decision digest
- Add cross-source reconciliation checks (price spread and outlier filtering)
- Add deterministic "known-bad conditions" fallback templates
- Add signed run manifests (digest hash + version) for auditability

## Phase 3: Regime Intelligence

Status: next

- Add explicit regime classifier:
  - trend, chop, panic, squeeze, macro-shock
- Introduce regime-specific prompt templates and confidence scaling
- Add event flags:
  - liquidation clusters, spread spikes, macro shock windows
- Build threshold optimization from historical replay

## Phase 4: Evaluation Harness

Status: next

- Build replay/backtest harness for pulse digests
- CI quality gate:
  - `python -m coinfox pulse replay --synthetic --horizon-steps 3`
- Evaluate rolling windows and walk-forward splits only
- Track model drift and calibration drift over time
- Add benchmark baselines:
  - naive trend-follow, mean-revert, neutral baseline

## Phase 5: Community Engine

Status: next

- PR template requiring metrics deltas for model changes
- Contributor scorecards (source quality and bug-fix reliability)
- Public changelog with before/after metric snapshots
- "Feature flag" framework for safe experimental rollout

## Phase 6: Free-Only Ops Hardening

Status: next

- Keep local-first routing (`ollama` first)
- Free-tier provider rotation and quota-aware routing
- No paid dependencies required for core monitoring
- Nightly QA run in GitHub Actions using synthetic fixtures

## High-Value Open Source Patterns To Borrow

All free/open source:

- `freqtrade/freqtrade`
  - Protections framework and hyperopt discipline for risk controls
- `jesse-ai/jesse`
  - Strong risk utilities and metrics-heavy workflow
- `vnpy/vnpy`
  - Mature modular architecture, risk-manager ecosystem pattern
- `mementum/backtrader`
  - Analyzer-driven evaluation architecture

## One-Pass Execution Checklist

- [x] Always-on run mode with live introspection
- [x] Self-heal gather retry + merge
- [x] Strange-market learning snapshot
- [x] Degraded fallback thought mode
- [x] Online metrics command
- [x] Pluggable provider registry + env-configurable provider order
- [x] Watchdog heartbeat health surface in `pulse status`
- [x] Governance baseline in `GOVERNANCE.md`
- [x] Lightweight automated issue triage workflow
- [x] Add per-source reliability scoring in digest
- [x] Add replay harness + CI quality gate
- [x] Add regime classifier and threshold tuner

## Commands For Daily Operation

- Start continuous monitoring:
  - `python -m coinfox pulse run --interval 300`
- Check provider + latest explanation:
  - `python -m coinfox pulse status`
- Force one cycle now:
  - `python -m coinfox pulse tick`
- Measure quality drift:
  - `python -m coinfox pulse metrics --window 200 --horizon-steps 6`
- Replay quality gate:
  - `python -m coinfox pulse replay --synthetic --horizon-steps 3`
- Tune regime thresholds:
  - `python -m coinfox pulse tune-regime`
