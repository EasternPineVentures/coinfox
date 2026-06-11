"""Resolve open trade calls against LIVE market prices.

Sweeps every open call and closes the ones the market has decided (target/stop
hit), crediting correct predictors and filling author track-record badges. Calls
on symbols we can't price yet (e.g. equities) are simply skipped — never wrongly
closed. Discussions are ignored entirely.

Run once:   PYTHONPATH=src python scripts/resolve_calls.py
On a loop:  schedule it every few minutes (cron / Task Scheduler).
"""
from __future__ import annotations

from coinfox.community.social import SocialStore
from coinfox.data import DataError, fetch_spot


def live_price(symbol: str):
    """symbol -> price, or None if we can't price it (so the sweep skips it).
    Uses the symbol-SAFE lookup so equities are skipped, never mispriced."""
    try:
        return fetch_spot(symbol)
    except DataError:
        return None


def main() -> None:
    store = SocialStore()
    summary = store.resolve_open_posts(live_price)
    print(
        f"checked {summary['checked']} open calls -> "
        f"resolved {len(summary['resolved'])}, expired {len(summary['expired'])}"
    )
    for item in summary["resolved"]:
        print(f"  resolved {item['post_id']} -> {item['outcome']}")


if __name__ == "__main__":
    main()
