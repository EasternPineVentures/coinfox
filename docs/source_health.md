# Source Health

Source health tells users whether CoinFox had fresh, usable data for a read.
It should be plain enough for a beginner to understand without reading logs.

## Allowed Statuses

### `healthy`

The source recently responded and contributed usable data.

Example: price candles loaded successfully and were included in the bias read.

### `degraded`

The source works sometimes but has recent failures.

Example: a source failed during the latest pulse, but other recent responses
were usable, so CoinFox continued with reduced context.

### `stale`

The source has not updated recently.

Example: a feed returns old data. CoinFox may still show the read, but the UI
should warn that part of the context is aging.

### `offline`

The source failed.

Example: the endpoint timed out, returned an error, or could not be parsed.

### `unknown`

There is not enough history yet.

Example: a new source was added and CoinFox has not collected enough responses
to judge reliability.

## Response Shape

CoinFox may return source health as an object:

```json
{
  "status": "degraded",
  "stale_sources": ["derivatives"],
  "notes": [
    "Derivatives context was unavailable; bias still uses spot and sentiment inputs."
  ]
}
```

## UI Guidance

- `healthy`: show normal read.
- `degraded`: show a small warning.
- `stale`: show that the read may be using old context.
- `offline`: make clear that a source did not contribute.
- `unknown`: explain that the source needs more history.

Source health is context, not a prediction by itself.
