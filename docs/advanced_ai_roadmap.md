# Advanced AI Roadmap

These ideas are future research directions for Eastern Pine Intelligence. They
should not derail the core CoinFox product: free data, explainable reads, source
health, replay gates, and plain-English output come first.

## Multi-Agent Debate

Future agents:

- Bull case
- Bear case
- Risk officer
- Judge

Purpose: use multiple perspectives to explain why CoinFox chose `LONG`,
`SHORT`, or `NEUTRAL`.

## Regime-Specific Models

Future regimes:

- Trending
- Choppy
- High-volatility
- News-driven
- Low-volume

Purpose: avoid using one model for every market condition.

## Source Credibility Model

Track sources by:

- uptime;
- latency;
- noise;
- replay usefulness;
- contradiction rate;
- contribution to correct and incorrect readouts.

## Community Model Leaderboard

Possible future fields:

- hit rate;
- drawdown;
- false-confidence rate;
- explainability score;
- source dependency count.

## Knowledge Graph

Example relationships:

```text
BTC -> crypto market
DXY -> dollar pressure
US10Y -> interest rates
NVDA -> AI risk appetite
SPY -> broad risk sentiment
```

Purpose: help CoinFox explain cross-market relationships in plain English.

## Guardrails

- Advanced models must be optional until proven.
- Every model change needs replay comparison.
- Plain-English output cannot be sacrificed for complexity.
- Community models should start experimental.
- No module should add live execution authority to CoinFox.
