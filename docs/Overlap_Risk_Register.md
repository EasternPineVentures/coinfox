# Overlap Risk Register

Date: 2026-05-31
Prepared for: EPV cross-repo consolidation and governance

## Scoring Model
- Impact: 1 (low) to 5 (critical)
- Likelihood: 1 (unlikely) to 5 (very likely)
- Risk Score = Impact x Likelihood

## Risk Register

| ID | Risk | Impact | Likelihood | Score | Current Owner | Mitigation | Target Date |
|---|---|---:|---:|---:|---|---|---|
| OR-01 | Router naming confusion across products (coinfox AI router naming overlaps with foxclaw brand semantics) | 3 | 4 | 12 | coinfox | Rename class/interface to neutral term (for example AIRouter/PulseRouter), update docs and import aliases | 2026-06-15 |
| OR-02 | Backtesting capability duplication between foxclaw and redshift_core creates divergent performance truth | 5 | 4 | 20 | redshift_core | Declare redshift_core as canonical backtest authority; map foxclaw modules to pre-screening only | 2026-06-30 |
| OR-03 | Execution boundary drift (intel layer accidentally owning execution semantics) | 5 | 3 | 15 | EPV architecture owner | Contract policy: coinfox outputs context only; execution intent forbidden in coinfox | 2026-06-10 |
| OR-04 | Relay coupling fragility between foxclaw and redshift_core integration lanes | 4 | 4 | 16 | redshift_core | Move toward explicit relay contract/event schema with versioning and failure modes | 2026-07-01 |
| OR-05 | foxclaw root-level regression test sprawl slows CI and obscures suite intent | 3 | 5 | 15 | foxclaw | Re-home tests to structured tests/ tree, split smoke/regression/perf markers | 2026-06-20 |
| OR-06 | Multi-requirements fragmentation in foxclaw increases environment drift | 3 | 4 | 12 | foxclaw | Consolidate dependencies (single runtime source + optional extras/dev constraints) | 2026-06-20 |
| OR-07 | Empty foxcoin repo creates planning ambiguity and namespace drag | 2 | 5 | 10 | EPV architecture owner | Assign charter or archive/remove repo | 2026-06-07 |
| OR-08 | Stale payload artifacts at EPV root can mislead audits and automation | 2 | 4 | 8 | EPV ops | Remove/archive payload files and document canonical data sources | 2026-06-07 |

## Top 3 Immediate Risks
1. OR-02 Backtesting divergence risk (score 20)
2. OR-04 Relay contract fragility (score 16)
3. OR-03 Execution boundary drift (score 15)

## Mitigation Playbooks

### OR-02: Backtesting divergence
- Define one canonical backtest output schema (fields, precision, timestamp rules).
- Create a compatibility adapter for foxclaw pre-screen modules.
- Enforce CI check: any strategy-result artifact must be reproducible in redshift_core.

### OR-04: Relay contract fragility
- Publish minimal v1 event contract (producer, consumer, schema, ack/failure behavior).
- Add version field and compatibility table.
- Add dead-letter handling and operator alert semantics.

### OR-03: Execution boundary drift
- Add static policy check in coinfox CI for prohibited execution primitives.
- Add architecture test gate requiring explicit approval for new cross-boundary modules.
- Add decision record template for contract changes.

## Acceptance Criteria (Done Definition)
- OR-02: A signed architecture note declares redshift_core as canonical backtest authority; foxclaw docs reflect this.
- OR-04: Relay contract v1 exists, versioned, with at least one integration validation test.
- OR-03: coinfox CI policy check exists and blocks prohibited execution semantics.
- OR-05/06: foxclaw test/dependency structure cleaned and verified by CI runtime matrix.

## Monitoring Cadence
- Weekly: review risk scores and owner status.
- Biweekly: verify contract and CI guardrail health.
- Monthly: retire closed risks and add newly discovered overlaps.

## coinfox Refactor Verification Notes
- CLI split and dispatcher modularization completed.
- Test status remains green after split: 59 passed (plus subtests), 1 external warning.
- Current modular sources of truth:
  - src/coinfox/__main__.py
  - src/coinfox/cli/_main.py
  - src/coinfox/cli/_parser.py
  - src/coinfox/cli/arena.py
  - src/coinfox/cli/pulse.py
  - src/coinfox/community/arena.py
  - src/coinfox/community/models.py
  - src/coinfox/community/market_hours.py
