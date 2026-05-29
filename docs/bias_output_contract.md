# Bias Output Contract

This document defines the target public shape for the CoinFox `/bias` API,
`python -m coinfox bias --json`, and the mobile Read tab.

CoinFox should sound like a transparent readout tool, not a command to buy or
sell. The output must explain the current market thesis, the confidence level,
the drivers, source health, and the reasoning area where the thesis weakens.

## Target JSON

```json
{
  "symbol": "BTCUSDT",
  "bias": "LONG",
  "confidence": 0.72,
  "probability_up": 0.64,
  "thesis": "BTC is leaning long because price is holding above recent support while market sentiment is improving.",
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
    },
    {
      "name": "Volume",
      "impact": "neutral",
      "plain_english": "Volume is not confirming a strong breakout yet."
    }
  ],
  "source_health": {
    "status": "healthy",
    "stale_sources": []
  },
  "timestamp": "2026-05-29T00:00:00Z"
}
```

## Required Fields

- `symbol`: market symbol, such as `BTCUSDT`.
- `bias`: one of `LONG`, `SHORT`, or `NEUTRAL`.
- `confidence`: model confidence from `0.0` to `1.0`.
- `probability_up`: estimated probability of upward movement over the selected horizon.
- `thesis`: one plain-English sentence explaining the current idea.
- `invalidation`: thesis-check area. Use `null` for `NEUTRAL` if no directional thesis is active.
- `drivers`: the main signals that contributed to the read.
- `source_health`: whether data sources are healthy, degraded, or stale.
- `timestamp`: UTC timestamp for the read.

## Wording Rule

The invalidation area is not an order instruction. It is a reasoning level where
the current idea starts to look weaker or wrong.

Preferred labels:

- Thesis check
- Thesis invalidation
- Bias weakens if
- Structure breaks if

Avoid wording that makes the field sound like account automation, exchange
execution, or personal risk advice.

## Compatibility Notes

The current Python contract may include additional fields such as `timeframe`,
`horizon`, `conviction`, `probability_down`, `regime_hint`, and `updated_at`.
Those are allowed while the public API converges on this target shape.
