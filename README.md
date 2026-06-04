# CoinFox

> **CoinFox is a free, keyless market intelligence terminal by Eastern Pine
> Intelligence, an open-source lab from Eastern Pine Ventures.**

CoinFox gathers free public market data, produces transparent `LONG`, `SHORT`,
or `NEUTRAL` bias readouts, explains the reasoning in plain English, and shows
what would weaken the current thesis. It is educational, open-source, and built
for community contribution.

[![CI](https://github.com/EasternPineVentures/coinfox/actions/workflows/ci.yml/badge.svg)](https://github.com/EasternPineVentures/coinfox/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

## What CoinFox Is

CoinFox is a transparent market readout tool. It does not place trades, control
accounts, or tell users what they must do. It provides directional bias,
confidence, top drivers, source health, and the area where the thesis starts to
weaken.

The public contract is intentionally simple:

- `LONG`: the current evidence leans upward.
- `SHORT`: the current evidence leans downward.
- `NEUTRAL`: the current evidence is mixed or not strong enough.

## Why It Exists

Most market tooling either hides behind paid APIs, buries the reasoning, or
pretends uncertainty does not exist. CoinFox takes the opposite path:

- free and keyless by default;
- plain-English first;
- transparent enough to inspect and improve;
- community-extensible without letting untrusted sources immediately affect the
  official readout.

## What It Does

- Fetches public market data from free sources.
- Produces `LONG`, `SHORT`, or `NEUTRAL` bias reads.
- Shows probability, confidence, top drivers, and thesis checks.
- Runs an always-on `pulse` loop for provider health, source health, replay
  gates, and regime tuning.
- Exposes an optional FastAPI surface for mobile and service integrations.
- Keeps source and model logic open for review.

## Repository Map & Handoff

> **Read this first when picking the project back up (human or AI agent).** It
> pins down *what* CoinFox is and *where* everything lives so parallel work does
> not create overlapping or duplicate files.

### Project identity

| Field | Value |
| --- | --- |
| Repo | `EasternPineVentures/coinfox` |
| Python package | `coinfox` (version in [src/coinfox/__init__.py](src/coinfox/__init__.py)) |
| Layout | **src-layout** - all importable code lives under [src/coinfox/](src/coinfox/) |
| Python | 3.9+ |
| Single source of truth for deps | [pyproject.toml](pyproject.toml) (`requirements.txt` just resolves it) |

> Important: CoinFox is **not** a flat module layout. If you remember top-level
> command modules beside `src/`, that is a stale picture - the
> code now lives under `src/coinfox/`. Always confirm against `src/coinfox/`
> before adding files.

### Where things live

| Path | What it is |
| --- | --- |
| [src/coinfox/__main__.py](src/coinfox/__main__.py) | CLI entrypoint (`python -m coinfox`) - all subcommands |
| [src/coinfox/model.py](src/coinfox/model.py) and [bias.py](src/coinfox/bias.py) | transparent weighted signal model + LONG/SHORT/NEUTRAL read |
| [src/coinfox/sources/](src/coinfox/sources/) | free public data feeds (prices, news, on-chain, macro, derivatives, and more) |
| [src/coinfox/ai/](src/coinfox/ai/) | AI router (`FoxClaw`), provider registry, pulse loop, regime, replay |
| [src/coinfox/community/](src/coinfox/community/) | arena: play-money "NY Fox Exchange", FC currency, ideas, bets, feed |
| [src/coinfox/feedback/](src/coinfox/feedback/) | anonymous feedback learning |
| [src/coinfox/api.py](src/coinfox/api.py) | FastAPI HTTP surface |
| [mobile/](mobile/) | Expo / React Native app with Read, Desk, Post, and Account tabs |
| [docs/](docs/) | contracts, contributor guides, roadmaps |
| [tests/](tests/) | test suite (run before every handoff) |

### Set up and verify

```bash
pip install -e .[api]      # core + API + everything tests need
python -m pytest -q        # or: python -m unittest discover -s tests
python -m coinfox bias --symbol BTCUSDT --json
```

### Product boundaries (keep scope clean)

CoinFox is the *public, keyless terminal*. **FoxClaw** (deeper operator
intelligence) and **Redshift** (simulation/replay) are separate products; see
[Eastern Pine Ecosystem](#eastern-pine-ecosystem). Note: the class named
`FoxClaw` inside [src/coinfox/ai/router.py](src/coinfox/ai/router.py) is just the
internal AI router, not the FoxClaw product.

## Quick Start

```bash
git clone https://github.com/EasternPineVentures/coinfox.git
cd coinfox
pip install -e .          # core (keyless) install
# pip install -e .[api]   # add the optional HTTP API server

python -m coinfox bias --symbol BTCUSDT --json
python -m coinfox pulse status
```

Optional local API:

```bash
pip install -e .[api]
uvicorn coinfox.api:app --reload --host 0.0.0.0 --port 8000
# or
python -m coinfox api --host 0.0.0.0 --port 8000
```

Local mobile/web clients should point at `http://localhost:8000` on the same
machine, or at your computer's LAN address from a physical phone. The intended
production split is `https://coinfox.cloud` for the public app and
`https://api.coinfox.cloud` for the API.

Production-style API server:

```bash
gunicorn -k uvicorn.workers.UvicornWorker coinfox.api:app --bind 0.0.0.0:8000
```

## Pulse Commands

```bash
# Provider health, watchdog state, latest AI read
python -m coinfox pulse status

# Same output as machine-readable JSON
python -m coinfox pulse status --json

# Explain what the command means
python -m coinfox pulse status --explain

# Force one pulse cycle now
python -m coinfox pulse tick

# Show recent pulse reads
python -m coinfox pulse history

# Online quality report from local history
python -m coinfox pulse metrics --window 200 --horizon-steps 6

# Deterministic replay quality gate for CI/offline checks
python -m coinfox pulse replay --synthetic --horizon-steps 3

# Tune regime detector thresholds on deterministic scenarios
python -m coinfox pulse tune-regime

# Summarize anonymous feedback events
python -m coinfox pulse feedback-report

# Always-on pulse loop
python -m coinfox pulse run --interval 300
```

## API Usage

The HTTP API exposes the same public bias read used by the CLI and the mobile
Read tab.

Local base URL:

```text
http://localhost:8000
```

Future production API base URL:

```text
https://api.coinfox.cloud
```

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/bias?symbol=BTCUSDT"
curl http://localhost:8000/terms
curl -X POST http://localhost:8000/feedback ^
  -H "Content-Type: application/json" ^
  -d "{\"anonymous_user_id\":\"local-random-id\",\"symbol\":\"BTCUSDT\",\"bias_shown\":\"LONG\",\"confidence_shown\":0.72,\"user_action\":\"thumbs_up\"}"
```

Full API notes live in [docs/api.md](docs/api.md).

## Social Links

The mobile app now supports shareable links for live reads and setup posts.
Local examples:

```text
http://localhost:8081?screen=read&symbol=BTCUSDT
http://localhost:8081?screen=desk&post=<post-id>
```

Future public links should use `https://coinfox.cloud`. The social feed and
permalink direction lives in [docs/social_permalink_plan.md](docs/social_permalink_plan.md).

## Plain-English Output Contract

CoinFox is designed so beginners can follow along without needing a finance
dictionary open in another tab.

Every major readout should explain:

- what the bias is;
- why the model leans that way;
- what would weaken the idea;
- which sources contributed;
- how confident the system is.

Target contract details live in [docs/bias_output_contract.md](docs/bias_output_contract.md).
Glossary terms live in [docs/terms.md](docs/terms.md).
Anonymous feedback learning is documented in [docs/feedback_learning.md](docs/feedback_learning.md).

## Thesis Invalidation

CoinFox uses thesis checks to show where the current idea starts to weaken. For
example, if CoinFox is leaning `SHORT`, the thesis may weaken above recent
resistance. If it is leaning `LONG`, the thesis may weaken below recent support.

The invalidation area is not an order instruction. It is a reasoning level where
the current idea starts to look weaker or wrong.

See [docs/thesis_invalidation.md](docs/thesis_invalidation.md).

## Source And Model Transparency

CoinFox favors inspectable logic over black-box claims. The model combines
signals such as trend, momentum, volume, volatility, sentiment, and source
health. Community sources start experimental, must pass health checks, and need
replay comparison before promotion into official bias logic.

Useful files:

- [src/coinfox/bias.py](src/coinfox/bias.py): public `LONG` / `SHORT` / `NEUTRAL` read.
- [src/coinfox/model.py](src/coinfox/model.py): transparent weighted signal model.
- [src/coinfox/ai/regime.py](src/coinfox/ai/regime.py): regime detector and tuner.
- [src/coinfox/ai/replay.py](src/coinfox/ai/replay.py): replay quality gate.
- [src/coinfox/community/guard.py](src/coinfox/community/guard.py): contribution safety checks.

## Contributing

CoinFox is built by Eastern Pine Intelligence for a contributor-friendly public
ecosystem. Start here:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [docs/source_contributor_guide.md](docs/source_contributor_guide.md)
- [docs/model_contributor_guide.md](docs/model_contributor_guide.md)
- [docs/plain_english_guide.md](docs/plain_english_guide.md)
- [GOVERNANCE.md](GOVERNANCE.md)
- [SECURITY.md](SECURITY.md)

## Eastern Pine Ecosystem

CoinFox is built by **Eastern Pine Intelligence**, the open-source technical lab
from **Eastern Pine Ventures**.

- **Eastern Pine Ventures**: company and umbrella.
- **Eastern Pine Intelligence**: open-source intelligence lab.
- **CoinFox**: public market intelligence terminal.
- **Planifier**: guided planning and beginner workflow surface.
- **FoxClaw**: guarded internal/operator intelligence system for safer strategy operation.
- **Redshift**: higher-risk simulation, replay, and execution-research lane.

Risk tiers and capital-authority boundaries are documented in
[docs/ecosystem_risk_tiers.md](docs/ecosystem_risk_tiers.md).

## Not Financial Advice

CoinFox is an experimental, educational market-read tool. It surfaces public
information and applies transparent heuristics. It does not know your financial
situation, risk tolerance, account size, tax situation, or time horizon.

You own every decision you make. Do not risk money you cannot afford to lose.

## License

MIT. See [LICENSE](LICENSE).
