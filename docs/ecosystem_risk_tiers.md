# EPV Ecosystem Risk Tiers

Date: 2026-06-04

This document defines how risk, execution authority, and product purpose are separated across the Eastern Pine ecosystem. The goal is not to make every system risk-free. The goal is to keep each kind of risk in the right lane, with clear guardrails.

## Plain-English Summary

- **CoinFox** is the public intelligence and social surface. It explains market reads and shared setups. It does not control capital.
- **Planifier** is the guided learning and planning surface. It can walk a beginner through a process step by step. It does not control capital.
- **FoxClaw** is the guarded operator intelligence system. It may still evaluate, paper-trade, learn, and later support safer controlled strategies, but it should run with conservative controls and strong receipts.
- **Redshift** is the higher-risk strategy research, simulation, replay, and execution-research lane. Aggressive experiments and leverage-heavy ideas belong here first, behind capital-box controls.

## Tier Map

| Tier | Product | Risk Posture | Capital Authority | Primary Job |
| --- | --- | --- | --- | --- |
| 0 | CoinFox | Public, educational, explainable | None | Show `LONG` / `SHORT` / `NEUTRAL` reads, thesis checks, source health, shared setups, and feedback |
| 1 | Planifier | Guided beginner workflow | None | Walk users through planning, setup discovery, journaling, and learning |
| 2 | FoxClaw | Guarded operator intelligence | Bounded and policy-gated only | Observe, decide, paper-trade, learn, self-repair within safer controls, and eventually operate lower-risk strategies |
| 3 | Redshift | Higher-risk research and simulation | Capital-box gated research lane | Backtest, replay, stress-test, simulate, and explore more aggressive strategy space |
| 4 | Eastern Pine Ventures | Company / umbrella | Business governance only | Own legal, operating, and portfolio-level decisions |

## Product Boundaries

### CoinFox

CoinFox can:

- Display public market intelligence.
- Explain a directional bias in plain English.
- Show a thesis check where the idea starts to weaken.
- Host social setup cards, comments, shared links, and anonymous feedback.
- Run replay and pulse checks for product quality.

CoinFox cannot:

- Place, route, modify, or cancel orders.
- Hold broker or exchange credentials.
- Decide account sizing or capital allocation.
- Become the canonical backtesting authority.

### Planifier

Planifier can:

- Teach workflows step by step.
- Help a beginner understand how to find, compare, and plan a setup.
- Track learning progress and checklist completion.
- Use context from CoinFox or FoxClaw as read-only educational input.

Planifier cannot:

- Place orders or control accounts.
- Turn a lesson into an execution command.
- Hide risk behind beginner-friendly language.

### FoxClaw

FoxClaw can:

- Run guarded operator workflows.
- Paper-trade and evaluate safer strategies.
- Learn from paper outcomes.
- Self-repair inside bounded, receipt-backed controls.
- Use Redshift context as context, not as automatic approval.
- Eventually support controlled trading strategies that are intentionally less aggressive than Redshift research.

FoxClaw should:

- Prefer safer strategies before risky ones.
- Keep live authority locked unless explicitly enabled by a separate policy gate.
- Preserve evidence receipts for every self-repair or tuning action.
- Separate strategy confidence from account authority.

FoxClaw cannot:

- Treat Redshift leverage posture as FoxClaw approval.
- Apply risky Redshift experiments directly to live behavior.
- Skip receipts, paper evidence, or policy gates because a signal looks strong.

### Redshift

Redshift can:

- Own canonical strategy simulation and replay.
- Test higher-risk ideas before they are trusted elsewhere.
- Explore leverage-heavy or aggressive strategy concepts under capital-box controls.
- Produce research context for FoxClaw.

Redshift should:

- Keep high-risk experimentation behind explicit simulation, paper, and capital-box boundaries.
- Emit clear context packets when FoxClaw consumes Redshift information.
- Make it obvious when a result is research-only.

Redshift cannot:

- Override FoxClaw operator safety gates.
- Act as a public social or educational product.
- Blur research results into user-facing CoinFox instructions.

## Cross-System Contract

```text
CoinFox -> FoxClaw / Redshift:
  intelligence artifacts only: bias, source health, thesis checks, social feedback, and public context

Planifier -> CoinFox / FoxClaw:
  guided workflows and learning steps only

Redshift -> FoxClaw:
  research context, replay results, and relay events only

FoxClaw -> Redshift:
  operator observations and paper-runtime context only
```

The key rule:

```text
Context is not approval.
```

If Redshift says an aggressive setup is interesting, FoxClaw may read that as context. FoxClaw still needs its own safer-policy gate before action. If CoinFox shows a bias, that bias is public intelligence, not execution authority.

## Risk Movement Rules

A strategy can move from Redshift toward FoxClaw only when:

- It has enough replay and paper evidence.
- It has clear failure modes.
- It has a safer FoxClaw profile that is less aggressive than the original Redshift experiment.
- It has bounded controls and receipts.
- A maintainer can explain the behavior in plain English.

A strategy should move back toward Redshift when:

- It needs higher leverage assumptions.
- It depends on fragile execution timing.
- It performs well only in narrow backtests.
- It causes unclear operator-state changes.
- It cannot explain why it acted.

## Codex Boundary Prompt

Use this when a task touches more than one EPV trading/intelligence repo:

```text
Pin the active project, path, branch, and repo before editing. CoinFox is public intelligence and social sharing only. Planifier is guided learning only. FoxClaw is guarded operator intelligence with safer strategies and bounded self-repair. Redshift is the higher-risk simulation, replay, and execution-research lane. Do not let context from one system become capital authority in another system without an explicit policy gate and receipt.
```

## Current Next Step

For CoinFox, the next product step is social read/setup sharing, public profiles, and API-backed feed contracts.

For FoxClaw, the next operator step is continued guarded paper evidence collection and bounded safer-strategy review.

For Redshift, the next research step is keeping aggressive experiments behind simulation/replay/capital-box gates while improving status and relay visibility.
