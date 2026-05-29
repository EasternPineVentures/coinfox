# Model Contributor Guide

Model Foxes improve scoring, replay, calibration, regime logic, and thesis
checks.

## Model Change Rules

- Keep logic explainable.
- Include tests for changed behavior.
- Run replay gates when a change affects `LONG`, `SHORT`, or `NEUTRAL` output.
- Show before/after metrics when possible.
- Avoid changes that increase confidence without evidence.

## Required Questions

Before opening a model PR, answer:

- What signal or behavior changed?
- Why should the read be better?
- Which market regime does this help?
- What could get worse?
- How did replay or tests respond?

## Quality Metrics

Useful metrics include:

- hit rate;
- weighted hit rate;
- brier-like calibration score;
- false-confidence rate;
- source dependency count;
- regime-specific accuracy.

## Promotion Path

1. Start experimental.
2. Add tests.
3. Run replay comparison.
4. Explain the user-visible behavior.
5. Get maintainer review.
6. Promote only when quality and safety are clear.
