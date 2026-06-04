# CoinFox Project Card

Date: 2026-05-31
Repo: EasternPineVentures/coinfox
Path: C:\\Users\\brend\\EPV_Dev\\coinfox
Branch baseline for this audit: main

## Project Role
CoinFox is EPV's public, keyless market-intelligence and community surface. It delivers transparent LONG/SHORT/NEUTRAL market readouts, plain-English thesis/invalidation context, source-health visibility, pulse monitoring, and a simulated community arena economy.

CoinFox is educational/intelligence software. It is not an execution runtime.

## Owns
- Public intelligence interfaces:
  - Python CLI via [src/coinfox/__main__.py](src/coinfox/__main__.py) and [src/coinfox/cli/_main.py](src/coinfox/cli/_main.py)
  - Optional FastAPI service via [src/coinfox/api.py](src/coinfox/api.py)
  - Mobile read/consumer app in [mobile](mobile)
- Bias model and explainability contract:
  - [src/coinfox/bias.py](src/coinfox/bias.py)
  - [src/coinfox/model.py](src/coinfox/model.py)
  - [docs/bias_output_contract.md](docs/bias_output_contract.md)
  - [docs/thesis_invalidation.md](docs/thesis_invalidation.md)
- Free-source ingestion and source-health logic:
  - [src/coinfox/sources](src/coinfox/sources)
  - [docs/source_health.md](docs/source_health.md)
- AI pulse/orchestration for intelligence context (non-execution):
  - [src/coinfox/ai](src/coinfox/ai)
  - [src/coinfox/ai/router.py](src/coinfox/ai/router.py)
- Community arena and simulated Gold economy:
  - [src/coinfox/community](src/coinfox/community)
  - [src/coinfox/community/arena.py](src/coinfox/community/arena.py)
- Anonymous feedback capture/reporting:
  - [src/coinfox/feedback](src/coinfox/feedback)

## Does Not Own
- Live order routing, broker/exchange account control, or execution lifecycle management.
- Venue adapters and operator execution orchestration (FoxClaw domain).
- Canonical backtesting/simulation authority and capital-box relay policy (Redshift domain).
- Plan orchestration/governance workflows expected in Planifier and The Grove.
- Real-money settlement, wallets, custody, deposits, withdrawals, or payments.

## Repo/Path
- Git repository: EasternPineVentures/coinfox
- Expected local path: C:\\Users\\brend\\EPV_Dev\\coinfox
- Source layout: src-layout Python package under [src/coinfox](src/coinfox)
- Primary packaging file: [pyproject.toml](pyproject.toml)
- Optional mobile app: [mobile/package.json](mobile/package.json)

## Current State
- Runtime shape is multi-surface in one repo:
  - Python CLI application
  - Optional FastAPI HTTP API
  - React Native (Expo) mobile client
- Installation/dependency state:
  - Python package metadata in [pyproject.toml](pyproject.toml)
  - [requirements.txt](requirements.txt) resolves editable install from pyproject
- API posture:
  - Read-focused API (`/bias`, `/terms`, `/health`, `/status`) with anonymous feedback write endpoint (`/feedback`)
  - Explicitly documented as non-execution in [docs/api.md](docs/api.md)

## Integration Points
- Internal module boundaries:
  - CLI command routing into bias/intel/pulse/community handlers
  - API reuses same bias contract and feedback models as CLI/data layer
  - Mobile Read tab consumes the bias contract defined in [docs/mobile_read_contract.md](docs/mobile_read_contract.md)
- External dependencies/services:
  - Public market data endpoints via source adapters in [src/coinfox/sources](src/coinfox/sources)
  - Optional AI provider APIs via router/provider modules in [src/coinfox/ai/providers](src/coinfox/ai/providers)
- Cross-product contract intent (documented in-repo):
  - CoinFox outputs intelligence artifacts; execution must remain outside CoinFox boundaries.

## Overlap Risks
- Brand/name confusion risk:
  - The class name `FoxClaw` in [src/coinfox/ai/router.py](src/coinfox/ai/router.py) can be confused with the separate FoxClaw product.
- Execution-boundary drift risk:
  - Arena "trade" wording and setup-map language can be misread as execution semantics if guardrails are not explicit in docs and CLI help.
- Backtest authority drift risk:
  - Replay/tuning utilities inside CoinFox could be misinterpreted as canonical strategy backtesting authority.
- Surface sprawl risk:
  - CLI + API + mobile + arena in one repo increases ownership ambiguity unless boundaries are repeated in docs.

## Next Cleanup Actions
1. Keep this card as a mandatory reference for project-scope decisions.
2. Add a short "CoinFox boundary" note in CLI help text where terms like `trade`, `call`, and `position` appear, clarifying simulation/intel-only context.
3. Rename the internal AI router class from `FoxClaw` to a neutral name (for example, `AIRouter`) and retain a temporary compatibility alias only if needed.
4. Add/maintain CI guardrails that flag execution primitives or account-control semantics in CoinFox code/docs.
5. Keep cross-product references at contract level only (inputs/outputs), with no direct coupling to external repos.

## Codex Prompt Boundary Rule For CoinFox
Use this rule in all CoinFox coding prompts:

"CoinFox is an intelligence and community simulation project only. Do not add or modify live execution, broker/exchange account control, order routing, settlement, or capital allocation code. Do not create dependencies on FoxClaw, Planifier, Redshift, or The Grove. Keep changes scoped to CoinFox docs, CLI/API intelligence outputs, source-health, pulse analytics, feedback, and community simulation behavior."
