# EPV Ecosystem Ownership Map

Date: 2026-05-31
Prepared for: EPV portfolio-level alignment

## Scope
This document defines repo-level ownership boundaries across the EPV stack so engineering, research, and operations can avoid duplicate builds and ownership drift.

## Repositories In Scope
- coinfox
- foxclaw
- redshift_core
- foxcoin

## Executive Summary
- coinfox is the public intelligence and community arena surface.
- foxclaw is the operator/runtime and execution-orchestration product surface.
- redshift_core is the strategy/backtest/relay core with capital-box controls.
- foxcoin currently has no implemented footprint and should be either scoped or archived.

## Domain Ownership Matrix

| Domain | Primary Owner | Secondary/Consumer | Out of Scope |
|---|---|---|---|
| Public market-intel CLI/API | coinfox | foxclaw, redshift_core consume outputs | Live execution control |
| Community social + arena economy | coinfox | none | Real-money settlement |
| AI pulse context loop | coinfox | foxclaw may consume outputs | Venue-level order logic |
| Operator workflows + runtime UX | foxclaw | none | Public OSS docs surface |
| Venue routing + execution orchestration | foxclaw | redshift_core integration | Public educational CLI |
| Canonical strategy abstraction | redshift_core | foxclaw | Social/community features |
| Canonical backtesting engine | redshift_core | foxclaw | Community arena scoring |
| Relay safety controls (capital box lane) | redshift_core | foxclaw | Product marketing/UI |
| Tokenomics layer | foxcoin (unassigned) | none | Current production runtime |

## System Boundary Contracts

### 1) coinfox -> foxclaw
- Contract: intelligence artifacts only (bias/read/context), no direct execution intent.
- Guarantee: educational and auditable outputs, not account-level control.
- Anti-pattern to avoid: embedding venue-specific routing behavior in coinfox.

### 2) foxclaw -> redshift_core
- Contract: strategy signal intake + relay into simulation/execution lanes with policy gates.
- Guarantee: execution requests remain behind redshift capital-box constraints.
- Anti-pattern to avoid: duplicating full strategy/backtest frameworks inside foxclaw.

### 3) coinfox <-> redshift_core
- Contract: optional intelligence enrichment only.
- Guarantee: redshift remains strategy/backtest authority.
- Anti-pattern to avoid: coinfox owning trade lifecycle semantics.

## Decision Rights (Who Decides)

| Decision Area | Final Decision Owner |
|---|---|
| Public API/CLI behavior for intel outputs | coinfox maintainer |
| Arena economy/rules | coinfox maintainer |
| Trading runtime behavior and venue adapters | foxclaw maintainer |
| Strategy schema and backtest methodology | redshift_core maintainer |
| Capital-box enforcement policy | redshift_core maintainer |
| Cross-repo contract changes | EPV architecture owner |

## RACI Snapshot

| Capability | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| Intel signal model tuning | coinfox | coinfox | foxclaw, redshift_core | EPV ops |
| Operator command center UX | foxclaw | foxclaw | redshift_core | coinfox |
| Backtest protocol changes | redshift_core | redshift_core | foxclaw | coinfox |
| Relay/event contract revisions | redshift_core | EPV architecture owner | foxclaw, coinfox | EPV ops |
| Tokenomics repo activation | foxcoin lead (TBD) | EPV architecture owner | coinfox | foxclaw, redshift_core |

## Ownership Guardrails
- Any module that can place/route/modify execution intent must live under foxclaw or redshift_core, never coinfox.
- Any public educational/user-facing market commentary surface belongs in coinfox, not foxclaw.
- Backtest truth source must be one stack: redshift_core.
- New cross-repo integrations require explicit contract note (producer, consumer, schema, failure mode).

## Immediate Actions
1. Keep coinfox focused on intelligence + community scope after CLI split finalization.
2. Keep redshift_core as canonical backtest/relay authority.
3. Run a foxclaw package hygiene pass (tests layout + dependency file consolidation).
4. Either define foxcoin charter or archive/remove it to prevent namespace drift.

## Source-of-Truth References (coinfox)
- CLI entrypoint: src/coinfox/__main__.py
- CLI dispatcher: src/coinfox/cli/_main.py
- CLI parser: src/coinfox/cli/_parser.py
- Arena handlers: src/coinfox/cli/arena.py
- Pulse handlers: src/coinfox/cli/pulse.py
- Arena domain: src/coinfox/community/arena.py
- Arena models: src/coinfox/community/models.py
- Market-hours logic: src/coinfox/community/market_hours.py
