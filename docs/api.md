# CoinFox API

The CoinFox API exposes the same public market read used by the CLI. It is
read-only except for anonymous feedback collection. It does not place trades,
control accounts, or require exchange keys.

Run locally:

```bash
python -m coinfox api --port 8000
```

Production-style example:

```bash
gunicorn -k uvicorn.workers.UvicornWorker coinfox.api:app --bind 0.0.0.0:8000
```

## GET /health

Returns API liveness.

```json
{
  "status": "ok",
  "timestamp": "2026-05-29T00:00:00+00:00"
}
```

## GET /bias

Returns the CoinFox `LONG` / `SHORT` / `NEUTRAL` read for a symbol. The response
matches the CLI bias contract used by `python -m coinfox bias --symbol BTCUSDT
--json`.

Query parameters:

- `symbol`: market symbol, default `BTCUSDT`.
- `timeframe`: one of `1m`, `5m`, `15m`, `1h`, `4h`, or `1d`.
- `horizon`: forecast horizon in candles.
- `limit`: number of candles to inspect.
- `use_derivs`: include derivatives context when available.

Example:

```json
{
  "symbol": "BTCUSDT",
  "bias": "LONG",
  "confidence": 0.72,
  "probability_up": 0.64,
  "thesis": "BTC is leaning long because price is holding above recent support.",
  "invalidation": {
    "label": "Thesis weakens below",
    "level": 67250.0,
    "reason": "A move below this zone would break the recent support structure.",
    "not_a_stop_loss": true
  },
  "drivers": [
    {
      "name": "Trend",
      "impact": "bullish",
      "plain_english": "Price is holding above the short-term moving average."
    }
  ],
  "source_health": {
    "status": "healthy",
    "stale_sources": []
  },
  "timestamp": "2026-05-29T00:00:00+00:00"
}
```

The invalidation object is a thesis check. It is a reasoning level where the
current idea starts to weaken, not an order instruction.

## GET /terms

Returns the shared beginner glossary used by docs, CLI explainability, and
mobile tooltips.

## POST /feedback

Stores anonymous user feedback for reporting. Feedback produces reports first;
it does not automatically rewrite model behavior.

Request:

```json
{
  "anonymous_user_id": "local-random-id",
  "symbol": "BTCUSDT",
  "bias_shown": "SHORT",
  "confidence_shown": 0.71,
  "user_action": "disagree",
  "comment": "Resistance is higher on my chart."
}
```

Response:

```json
{
  "ok": true,
  "id": 123
}
```
