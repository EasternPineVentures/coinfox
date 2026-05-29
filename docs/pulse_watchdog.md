# Pulse Watchdog

The CoinFox pulse system should be transparent and auditable. Operators and
contributors should be able to answer:

- Is the pulse loop alive?
- Which sources are healthy?
- What was the last read?
- Did replay quality change?
- Were any errors hidden from the user?

## Target Append-Only Logs

```text
data/pulse_heartbeat.json
data/decision_log.jsonl
data/source_health.jsonl
data/replay_quality.jsonl
```

The heartbeat can be a current-state JSON file. Decision, source-health, and
replay-quality logs should be append-only JSONL so audits can inspect history.

## Heartbeat Shape

```json
{
  "last_tick": "2026-05-29T00:00:00Z",
  "status": "healthy",
  "last_symbol": "BTCUSDT",
  "last_bias": "LONG",
  "errors_last_hour": 0
}
```

## Decision Log Shape

```json
{
  "timestamp": "2026-05-29T00:00:00Z",
  "symbol": "BTCUSDT",
  "bias": "LONG",
  "confidence": 0.72,
  "invalidation_level": 67250,
  "human_readable": "BTC is leaning long because price is holding above recent support while sentiment is improving."
}
```

## Operator Rules

- Logs should preserve evidence instead of hiding failed reads.
- Source health should distinguish stale, missing, degraded, and healthy states.
- Replay quality should be visible before a model change is promoted.
- A watchdog warning should be plain English and actionable.
- Pulse observability must not imply live trading authority.
