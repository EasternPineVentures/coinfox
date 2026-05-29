# Source Contributor Guide

Source Foxes improve CoinFox by adding, repairing, or reviewing market data
sources.

## Source Rules

- Default CoinFox sources should be free and keyless whenever possible.
- A source must fail gracefully.
- A source must include enough context for users to understand what it measures.
- A source must not require users to provide exchange keys.
- A source must not immediately affect official bias output.

## Source Quarantine Model

New community sources start as experimental. They must pass source health checks
and replay comparison before promotion into official CoinFox bias.

Promotion requires:

- clear source purpose;
- terms and attribution notes;
- timeout and failure handling;
- tests or fixtures;
- replay comparison against baseline;
- maintainer review.

## Good Source PRs Include

- The source module under `src/coinfox/sources/`.
- Registration in the intel aggregator if appropriate.
- Plain-English rendering in terminal/mobile docs if user-facing.
- A note explaining what market question the source helps answer.
- Tests for parsing and graceful failure.

## Example Market Questions

- Is liquidity improving or drying up?
- Is sentiment changing faster than price?
- Are macro signals supporting or contradicting the read?
- Is a move broad or isolated to one venue?
