# Mobile Read Contract

The mobile Read tab should be able to render the `/bias` response without
guessing what a field means. This contract describes the fields the mobile UI
expects from CoinFox.

## Example Response

```json
{
  "symbol": "BTCUSDT",
  "bias": "LONG",
  "confidence": 0.72,
  "probability_up": 0.64,
  "probability_down": 0.36,
  "thesis": "BTC is leaning long because price is holding above recent support while market sentiment is improving.",
  "invalidation": {
    "type": "price_below",
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
    "stale_sources": [],
    "notes": []
  },
  "timestamp": "2026-05-29T00:00:00Z"
}
```

## Fields

- `symbol`: the market being read, such as `BTCUSDT`.
- `bias`: one of `LONG`, `SHORT`, or `NEUTRAL`.
- `confidence`: how strongly the current signals agree, from `0.0` to `1.0`.
- `probability_up`: estimated upward probability for the configured horizon.
- `probability_down`: estimated downward probability for the configured horizon.
- `thesis`: one plain-English sentence that explains the current idea.
- `invalidation`: the thesis-check area for directional reads. It should be
  `null` for `NEUTRAL`.
- `drivers`: the main signals behind the read.
- `source_health`: whether the data sources are usable.
- `timestamp`: when the read was produced, in UTC or ISO-compatible format.

## Invalidation Rules

The mobile app labels this area as a thesis check. It is a reasoning level where
the current idea starts to look weaker or wrong.

`invalidation.not_a_stop_loss` must always be `true` when the invalidation object
is present. The mobile app should never treat this field as an account action,
exchange instruction, or personal risk rule.

## Driver Rules

Every driver should include:

- `name`: short label, such as `Trend` or `Volume`.
- `impact`: plain direction label such as `bullish`, `bearish`, or `neutral`.
- `plain_english`: one beginner-friendly sentence explaining the signal.

## Source Health Rules

The mobile app may show a source warning if `source_health.status` is not
`healthy`. See [source_health.md](source_health.md) for allowed statuses.
