"""CLI entrypoint: `python -m coinfox`."""

from __future__ import annotations

import argparse
import sys
import time

from rich.console import Console
from rich.live import Live

from .credits import render_credits
from .dashboard import render_call, render_intel, render_verdict
from .data import DataError, fetch_24h_stats, fetch_fear_greed, fetch_klines, fetch_price
from .intel import gather
from .model import evaluate
from .new_source import scaffold
from .trade import make_idea


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="coinfox",
        description="🦊 coinfox — a fox that watches BTC and estimates the odds. Free BTC info for everyone.",
    )
    sub = p.add_subparsers(dest="cmd")

    # `watch` (also the default if no subcommand given)
    w = sub.add_parser("watch", help="signals + probability verdict (default)")
    _watch_args(w)

    # `intel`
    i = sub.add_parser("intel", help="full firehose of BTC info from many sources")
    i.add_argument("--no-news", action="store_true")
    i.add_argument("--no-social", action="store_true")

    # `call`
    c = sub.add_parser("call", help="actionable trade idea: entry, stop, target, size")
    _watch_args(c)
    c.add_argument("--kelly-cap", type=float, default=2.0,
                   help="max %% of bankroll to risk (default 2.0)")
    c.add_argument("--kelly-scale", type=float, default=0.25,
                   help="Kelly fraction to use (default 0.25 = quarter-Kelly)")
    c.add_argument("--atr-stop", type=float, default=1.5,
                   help="stop distance in ATRs (default 1.5)")
    c.add_argument("--atr-target", type=float, default=2.5,
                   help="target distance in ATRs (default 2.5)")

    # `all`
    a = sub.add_parser("all", help="verdict + call + full intel together")
    _watch_args(a)

    # `credits` — Hall of Foxes
    sub.add_parser("credits", help="🦊 show contributor credits (the Hall of Foxes)")

    # `new-source` — scaffold a new community source module
    ns = sub.add_parser("new-source",
                        help="scaffold a new source module (you in CONTRIBUTORS, auto-registered)")
    ns.add_argument("name", help="source name (e.g. 'lightning-stats')")
    ns.add_argument("--author", required=True, help="your GitHub handle (no @)")
    ns.add_argument("--name-display", default=None, help="display name (default: same as --author)")
    ns.add_argument("--endpoint", default="https://api.example.com/btc")
    ns.add_argument("--why", default="TODO: what does this tell us about BTC?")
    ns.add_argument("--contribution", default=None)

    # legacy top-level flags (so `python -m coinfox` still works)
    _watch_args(p)
    return p


def _watch_args(p):
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
    candles = fetch_klines(symbol=args.symbol, interval=args.timeframe, limit=args.limit)
    price = fetch_price(args.symbol)
    try:
        stats = fetch_24h_stats(args.symbol)
    except DataError:
        stats = None
    fng = fetch_fear_greed()
    funding = basis = None
    if getattr(args, "use_derivs", False):
        from .sources.derivatives import fetch_derivatives
        d = fetch_derivatives()
        funding = d.avg_funding
        basis = d.basis_pct
    verdict = evaluate(candles, fng, horizon=args.horizon,
                       funding_rate=funding, basis_pct=basis)
    return candles, price, stats, fng, verdict


def _verdict_panel(args, console):
    _, price, stats, fng, verdict = _gather_view(args)
    return render_verdict(verdict, args.symbol, args.timeframe, price, stats, fng)


def _call_panel(args, console):
    candles, _, _, _, verdict = _gather_view(args)
    idea = make_idea(
        verdict, candles, args.timeframe,
        atr_stop_mult=getattr(args, "atr_stop", 1.5),
        atr_target_mult=getattr(args, "atr_target", 2.5),
        kelly_cap_pct=getattr(args, "kelly_cap", 2.0),
        kelly_scale=getattr(args, "kelly_scale", 0.25),
    )
    return render_call(idea)


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    console = Console()
    cmd = args.cmd or "watch"

    try:
        if cmd == "intel":
            intel = gather()
            console.print(render_intel(intel))
            return 0

        if cmd == "credits":
            console.print(render_credits())
            return 0

        if cmd == "new-source":
            try:
                path = scaffold(
                    name=args.name,
                    author_handle=args.author,
                    author_name=args.name_display or args.author,
                    endpoint=args.endpoint,
                    why=args.why,
                    contribution=args.contribution,
                )
            except FileExistsError as e:
                console.print(f"[bold red]error:[/] {e}")
                return 1
            console.print(f"[bold green]✓ created[/] {path}")
            console.print("[dim]next steps:[/]")
            console.print("  1. fill in the TODO in the new module")
            console.print("  2. add a render block in dashboard.py::render_intel (optional)")
            console.print("  3. run [cyan]python -m coinfox intel[/] to see it live")
            console.print("  4. run [cyan]python -m coinfox credits[/] to see your name 🦊")
            return 0

        if cmd == "call":
            console.print(_call_panel(args, console))
            return 0

        if cmd == "all":
            candles, price, stats, fng, verdict = _gather_view(args)
            console.print(render_verdict(verdict, args.symbol, args.timeframe, price, stats, fng))
            idea = make_idea(verdict, candles, args.timeframe)
            console.print(render_call(idea))
            console.print(render_intel(gather()))
            return 0

        # watch (default)
        if getattr(args, "watch_loop", False):
            with Live(_verdict_panel(args, console), console=console,
                      refresh_per_second=2, screen=False) as live:
                while True:
                    time.sleep(max(1, args.interval))
                    try:
                        live.update(_verdict_panel(args, console))
                    except DataError as e:
                        console.print(f"[yellow]data error (will retry):[/] {e}")
        else:
            console.print(_verdict_panel(args, console))
        return 0

    except KeyboardInterrupt:
        console.print("\n[dim]fox went to sleep. 🦊[/]")
        return 0
    except DataError as e:
        console.print(f"[bold red]data error:[/] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
