# Feedback Learning

CoinFox should learn from user feedback without collecting sensitive personal
data by default.

## Privacy Rule

CoinFox should not store personal identity by default. Feedback should use a
random anonymous local ID unless a user explicitly opts into an account system
later.

No default feedback event should include email, legal name, exchange account,
API key, IP address, wallet seed, or private trading logs.

## Future Event Shape

```json
{
  "anonymous_user_id": "local-random-id",
  "symbol": "BTCUSDT",
  "bias_shown": "SHORT",
  "confidence_shown": 0.71,
  "user_feedback": "disagree",
  "user_invalidation_level": 70800,
  "comment": "Resistance is higher on my chart.",
  "timestamp": "2026-05-29T00:00:00Z"
}
```

## Feedback Types

- `useful`: the read helped the user think clearly.
- `not_useful`: the read was confusing or unhelpful.
- `agree`: the user agrees with the direction.
- `disagree`: the user disagrees with the direction.
- `adjusted_invalidation`: the user changed the thesis-check level.
- `source_issue`: the user noticed stale, missing, or wrong data.

## Implemented First Step

CoinFox now includes local feedback storage and a maintainer report command:

```bash
python -m coinfox pulse feedback-report
```

The optional API exposes:

```text
POST /feedback
```

The first implementation stores events in local SQLite and reports aggregate
patterns. It does not collect personal identity by default.

## Learning Rule

At first, feedback should produce reports, not automatically rewrite model
behavior.

Report command:

```bash
python -m coinfox pulse feedback-report
```

Example report:

```text
Users adjusted BTC short invalidation 14 times.
Median user level was 1.2% higher than the model level.
Suggested change: widen BTC short invalidation during high-volatility regimes.
```

## Promotion Rule

A feedback-derived change should require:

- enough events to avoid overfitting;
- anonymized reporting only;
- replay comparison against baseline;
- plain-English explanation of what changed;
- maintainer review before live behavior changes.
