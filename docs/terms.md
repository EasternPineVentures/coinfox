# CoinFox Glossary

These definitions are written for CLI help, mobile tooltips, docs, and
contributor checks. Keep them plain, short, and beginner-friendly.

The shared JSON copy lives at `src/coinfox/assets/terms.json`.

### LONG

A read that says the current evidence leans upward.

### SHORT

A read that says the current evidence leans downward.

### NEUTRAL

A read that says the evidence is mixed, weak, or not clear enough for a
directional lean.

### Bias

The current directional lean: `LONG`, `SHORT`, or `NEUTRAL`.

### Confidence

How strongly CoinFox trusts the read. High confidence means the signals agree
more. Low confidence means the picture is mixed.

### Conviction

Another word for strength of belief in the read. CoinFox keeps it separate from
certainty because markets can still surprise any model.

### Probability

An estimate of how likely an outcome is. A probability is not a promise.

### Thesis

The plain-English idea behind the read.

### Invalidation

The area where the current idea starts to look wrong. If CoinFox is leaning
`SHORT`, the invalidation area may be above a recent resistance zone. This is a
thesis check, not an order instruction.

### Support

A price area where buyers have recently appeared.

### Resistance

A price area where sellers have recently appeared.

### Order Block

A price zone where a large amount of buying or selling may have happened before.
CoinFox treats it as context, not proof.

### Trend

The general direction price has been moving.

### Momentum

How strongly price is moving in its current direction.

### Volume

How much trading activity happened during a period.

### Volatility

How much price is moving around. High volatility means price is changing faster
or more widely than usual.

### Regime

The current market environment, such as trending, choppy, high-volatility,
news-driven, or low-volume.

### Replay Gate

A test that replays stored reads against later market data to check whether the
system is behaving well enough to trust for review.

### Regime Tuner

A tool that adjusts regime thresholds using deterministic examples.

### Paper Trade

A simulated trade used for research and learning. It does not place a real order.

### Source Health

Whether data sources are fresh, reachable, and usable.

### Driver

A signal that pushed the read in one direction, such as trend, volume, or
sentiment.

### Macro

Big-picture market context, such as rates, the dollar, indexes, commodities, or
economic events.

### Micro

Near-term market context, such as recent candles, local support and resistance,
volume, and short-horizon momentum.

### Tape Check

A quick read of recent price and volume behavior.

### Watchdog

A health monitor that checks whether the pulse loop and data sources are still
working.

### Pulse

CoinFox's always-on market read loop. It checks sources, gathers context, and
stores recent reads.

### Liquidity

How easy it is for a market to absorb buying or selling without moving too much.

### Risk/Reward

A comparison between how much an idea could lose and how much it could gain.

### Drawdown

A drop from a previous high point in account value, strategy value, or simulated
performance.

### False Confidence

When a model sounds sure but the evidence is weak, stale, or incomplete.

### Backtest

A historical test that checks how a method would have behaved on past data.

### Synthetic Data

Generated test data used to exercise the system when real market history is not
needed or is not available.
