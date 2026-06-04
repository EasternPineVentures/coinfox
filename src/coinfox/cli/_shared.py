"""Shared helpers used across CLI submodules."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def _watch_args(p) -> None:
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--timeframe", "-t", default="1h",
                   choices=["1m", "5m", "15m", "1h", "4h", "1d"])
    p.add_argument("--horizon", type=int, default=4)
    p.add_argument("--limit", type=int, default=250)
    p.add_argument("--watch-loop", action="store_true",
                   dest="watch_loop", help="continuously refresh")
    p.add_argument("--interval", type=int, default=30)
    p.add_argument("--use-derivs", action="store_true",
                   help="fold funding/basis into the probability model")


def _gather_view(args):
    from ..data import DataError, fetch_24h_stats, fetch_fear_greed, fetch_klines, fetch_price
    from ..model import evaluate

    candles = fetch_klines(symbol=args.symbol, interval=args.timeframe, limit=args.limit)
    price = fetch_price(args.symbol)
    try:
        stats = fetch_24h_stats(args.symbol)
    except DataError:
        stats = None
    fng = fetch_fear_greed()
    funding = basis = None
    if getattr(args, "use_derivs", False):
        from ..sources.derivatives import fetch_derivatives
        d = fetch_derivatives()
        funding = d.avg_funding
        basis = d.basis_pct
    verdict = evaluate(candles, fng, horizon=args.horizon,
                       funding_rate=funding, basis_pct=basis)
    return candles, price, stats, fng, verdict


def _verdict_panel(args, console):
    from ..dashboard import render_verdict

    _, price, stats, fng, verdict = _gather_view(args)
    return render_verdict(verdict, args.symbol, args.timeframe, price, stats, fng)


def _call_panel(args, console):
    from ..dashboard import render_call
    from ..trade import make_idea

    candles, _, _, _, verdict = _gather_view(args)
    idea = make_idea(
        verdict, candles, args.timeframe,
        atr_stop_mult=getattr(args, "atr_stop", 1.5),
        atr_target_mult=getattr(args, "atr_target", 2.5),
        kelly_cap_pct=getattr(args, "kelly_cap", 2.0),
        kelly_scale=getattr(args, "kelly_scale", 0.25),
    )
    return render_call(idea)


def _bias_color(bias: str) -> str:
    return {"long": "bold green", "short": "bold red", "neutral": "bold yellow"}.get(bias, "white")


def _age_text(ts: int) -> str:
    age_s = max(0, int(time.time()) - int(ts))
    if age_s < 3600:
        return f"{age_s // 60}m ago"
    if age_s < 86400:
        return f"{age_s // 3600}h ago"
    return f"{age_s // 86400}d ago"


def _resolve_arena_user(arena, explicit_user: str | None) -> str:
    from ..community.arena import ArenaError

    if explicit_user:
        return arena.ensure_user(explicit_user).handle
    handle = arena.identity()
    if not handle:
        raise ArenaError("no arena identity set; run `coinfox arena whoami --user yourname` first")
    return arena.ensure_user(handle).handle
