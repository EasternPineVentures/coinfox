# CLI Explainability

CoinFox public commands should explain themselves in plain English.

Implemented now:

```bash
python -m coinfox pulse status --explain
python -m coinfox pulse tick --explain
python -m coinfox pulse history --explain
python -m coinfox pulse metrics --explain
python -m coinfox pulse replay --explain
python -m coinfox pulse tune-regime --explain
python -m coinfox pulse feedback-report --explain
python -m coinfox pulse run --explain
```

Each explain view should answer:

1. What the command does.
2. What the output means.
3. What a beginner should pay attention to.
4. Any safety note.

## Command Notes

### `pulse status`

Shows provider routing, watchdog health, source reliability, regime context, and
the latest AI read. Beginners should look for stale health, missing sources,
and whether the latest read is high-confidence or mixed.

### `pulse replay`

Runs stored or synthetic pulse reads through a replay gate. Beginners should
look at sample size, hit rate, and brier-like score. A passing replay gate is a
quality check, not a guarantee.

### `pulse tune-regime`

Tunes deterministic regime thresholds. Beginners should compare baseline versus
best accuracy and read the recommended config as a model setting, not a market
prediction.

### `pulse feedback-report`

Summarizes anonymous feedback events. Beginners should read it as maintainer
input, not as an automatic model update.

## Next Step

Extend the same `--explain` pattern to `bias`, `watch`, `call`, and `arena`
commands after their public wording is reviewed.
