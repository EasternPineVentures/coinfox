# Contributing To CoinFox

CoinFox is the first public open-source market intelligence product from
**Eastern Pine Intelligence**, the technical lab from **Eastern Pine Ventures**.

The goal is simple: help users understand whether a market looks `LONG`,
`SHORT`, or `NEUTRAL`, show the evidence, and explain what would weaken the
current thesis.

## Contributor Lanes

- **Source Fox**: adds or improves market data sources.
- **Glossary Fox**: improves plain-English explanations.
- **Model Fox**: improves scoring, replay, and regime logic.
- **UI Fox**: improves mobile/web/terminal display.
- **Test Fox**: adds regression tests and quality gates.
- **Research Fox**: summarizes papers, market structure, and model ideas.
- **Safety Fox**: reviews risky changes and checks user protection.

## Project Values

1. **Free first**. Default sources should work without paid keys.
2. **Plain-English first**. Users should understand what the read means.
3. **Transparent**. Signals, source health, and confidence should be inspectable.
4. **Educational**. CoinFox provides context, not personal financial advice.
5. **Guarded openness**. Good contributors should move quickly; secrets, spam,
   unsafe automation, and misleading model changes should be stopped early.

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/coinfox.git
cd coinfox
pip install -r requirements.txt
pip install -e .
python -m coinfox bias --json
python -m coinfox pulse status
python -m unittest discover -s tests -v
```

## Source Quarantine Model

New community sources do not immediately affect official CoinFox bias. They
start as experimental, must pass source health checks, and need replay comparison
before promotion.

See [docs/source_contributor_guide.md](docs/source_contributor_guide.md).

## Model Change Model

Changes to scoring, replay, regime logic, confidence, or thesis invalidation
must explain the user-visible behavior and include tests. If the change affects
`LONG`, `SHORT`, or `NEUTRAL`, include a replay comparison when possible.

See [docs/model_contributor_guide.md](docs/model_contributor_guide.md).

## Plain-English Requirement

Any user-visible term that may confuse a beginner should be defined in
[docs/terms.md](docs/terms.md) or explained near the output. CLI and mobile
surfaces should prefer "thesis check", "bias weakens if", and "source health"
over jargon.

See [docs/plain_english_guide.md](docs/plain_english_guide.md).

## Tests

Run the relevant checks:

```bash
python -m coinfox pulse status --json | python -m json.tool
python -m coinfox pulse replay --synthetic --horizon-steps 3
python -m pytest tests/test_json_utils.py -v
python -m unittest discover -s tests -v
```

For mobile changes:

```bash
cd mobile
npm.cmd run typecheck
npx expo export --platform web
```

## Pull Request Checklist

- [ ] I explained the change in plain language.
- [ ] I did not include secrets, tokens, private keys, seed phrases, or private logs.
- [ ] I did not add a required paid API dependency.
- [ ] I kept CoinFox educational and readout-focused.
- [ ] I added or updated tests for logic changes.
- [ ] I updated docs for user-facing behavior.
- [ ] I added glossary entries for unfamiliar user-facing terms.
- [ ] I included source and terms notes for data-source changes.
- [ ] I ran relevant checks or explained why I could not.

## Anti-Bad-Actor Plan

1. Pull request template required.
2. Tests required for logic changes.
3. Source and model changes require maintainer review.
4. New sources start experimental.
5. Security checks run in CI.
6. Reputation and trust ladder documented.
7. Optional future staking or bounty systems may be explored later, but no token
   staking is required for normal contribution.

## Community Guard

Use the issue templates for bugs, features, data sources, and bias reviews.
Every request and pull request may be checked by the community guard:

```bash
python -m coinfox.community.guard --title "request title" --body "request body"
```

The guard flags likely secrets, credential requests, prompt-injection wording,
destructive commands, link floods, repetitive spam, and sensitive-file changes.

## Code Of Conduct

Be kind and direct. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

By contributing, you agree your contributions are licensed under the MIT License.
