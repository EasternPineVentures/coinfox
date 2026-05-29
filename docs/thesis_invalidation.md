# Thesis Invalidation

Thesis invalidation is CoinFox's way of saying: "Here is where this idea starts
to look weaker."

It is not an order instruction, account instruction, or exchange action. It is a
reasoning level for the current `LONG` or `SHORT` read.

## How CoinFox Should Phrase It

Use:

- Thesis check
- Thesis invalidation
- Bias weakens if
- Structure breaks if

Avoid making it sound like CoinFox is controlling a user's account.

## First Heuristic

The first version can use recent swing levels plus a small buffer:

```python
def compute_invalidation(bias, current_price, recent_swing_high, recent_swing_low, buffer_percent=0.005):
    buffer = current_price * buffer_percent

    if bias == "SHORT":
        return {
            "type": "price_above",
            "level": round(recent_swing_high + buffer, 2),
            "reason": "Price moving above this area would weaken the short thesis because it breaks above recent resistance.",
            "not_a_stop_loss": True,
        }

    if bias == "LONG":
        return {
            "type": "price_below",
            "level": round(recent_swing_low - buffer, 2),
            "reason": "Price moving below this area would weaken the long thesis because it breaks below recent support.",
            "not_a_stop_loss": True,
        }

    return None
```

## How Feedback Can Improve It

At first, CoinFox should only report feedback patterns. It should not
automatically rewrite model behavior.

Useful future comparisons:

- model invalidation level versus user-adjusted level;
- volatility regime when users widen or tighten the level;
- source health when users disagree;
- whether high-confidence reads fail near the thesis-check area.

The first learning loop should produce reports for maintainers. Promotion into
live behavior should require tests, replay comparison, and maintainer review.
