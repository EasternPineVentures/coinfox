"""CoinFox CLI entry point - `main()` dispatcher."""

from __future__ import annotations

import sys
import time

from rich.console import Console
from rich.live import Live

from ._parser import _build_parser
from ._shared import _call_panel, _gather_view, _verdict_panel
from .app import _run_api_server
from .arena import (
    _render_arena_balance,
    _render_arena_bet,
    _render_arena_borrow,
    _render_arena_comment,
    _render_arena_exit,
    _render_arena_feed,
    _render_arena_ideas,
    _render_arena_ledger,
    _render_arena_leaderboard,
    _render_arena_market,
    _render_arena_positions,
    _render_arena_post,
    _render_arena_posts,
    _render_arena_profile,
    _render_arena_repay,
    _render_arena_rescue,
    _render_arena_resolve,
    _render_arena_say,
    _render_arena_show,
    _render_arena_stats,
    _render_arena_trade,
    _render_arena_whoami,
)
from .pulse import (
    _render_bias,
    _render_churn_history,
    _render_churn_metrics,
    _render_churn_replay,
    _render_churn_run,
    _render_churn_status,
    _render_churn_tick,
    _render_churn_tune_regime,
    _render_pulse_explain,
    _render_pulse_feedback_report,
)
from ..community.arena import ArenaError
from ..data import DataError


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "churn":
        argv[0] = "pulse"
    args = _build_parser().parse_args(argv)
    console = Console()
    cmd = args.cmd or "watch"

    try:
        if cmd == "intel":
            from ..intel import gather
            from ..dashboard import render_intel
            intel = gather()
            console.print(render_intel(intel))
            return 0

        if cmd == "bias":
            return _render_bias(args, console)

        if cmd == "credits":
            from ..credits import render_credits
            console.print(render_credits())
            return 0

        if cmd == "new-source":
            from ..new_source import scaffold
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
            console.print(f"[bold green]\u2713 created[/] {path}")
            console.print("[dim]next steps:[/]")
            console.print("  1. fill in the TODO in the new module")
            console.print("  2. add a render block in dashboard.py::render_intel (optional)")
            console.print("  3. run [cyan]python -m coinfox intel[/] to see it live")
            console.print("  4. run [cyan]python -m coinfox credits[/] to see your name \U0001f98a")
            return 0

        if cmd == "api":
            return _run_api_server(args, console)

        if cmd in {"pulse", "churn"}:
            pulse_cmd = getattr(args, "pulse_cmd", None) or "status"
            if getattr(args, "explain", False):
                return _render_pulse_explain(pulse_cmd, console)
            if pulse_cmd == "status":
                return _render_churn_status(args, console)
            if pulse_cmd == "tick":
                return _render_churn_tick(console)
            if pulse_cmd == "history":
                return _render_churn_history(getattr(args, "n", 10), console)
            if pulse_cmd == "metrics":
                return _render_churn_metrics(
                    getattr(args, "window", 200),
                    getattr(args, "horizon_steps", 6),
                    getattr(args, "neutral_band_pct", 0.20),
                    console,
                )
            if pulse_cmd == "replay":
                return _render_churn_replay(args, console)
            if pulse_cmd == "tune-regime":
                return _render_churn_tune_regime(console)
            if pulse_cmd == "feedback-report":
                return _render_pulse_feedback_report(args, console)
            if pulse_cmd == "run":
                return _render_churn_run(getattr(args, "interval", 300), console)
            return _render_churn_status(args, console)

        if cmd == "arena":
            arena_cmd = getattr(args, "arena_cmd", None) or "ideas"
            if arena_cmd == "whoami":
                return _render_arena_whoami(args, console)
            if arena_cmd == "balance":
                return _render_arena_balance(args, console)
            if arena_cmd == "profile":
                return _render_arena_profile(args, console)
            if arena_cmd == "say":
                return _render_arena_say(args, console)
            if arena_cmd == "posts":
                return _render_arena_posts(
                    getattr(args, "user", None), getattr(args, "n", 20), console
                )
            if arena_cmd == "feed":
                return _render_arena_feed(
                    getattr(args, "user", None), getattr(args, "n", 20), console
                )
            if arena_cmd == "market":
                return _render_arena_market(console)
            if arena_cmd == "leaderboard":
                return _render_arena_leaderboard(getattr(args, "n", 10), console)
            if arena_cmd == "ideas":
                return _render_arena_ideas(
                    getattr(args, "all", False), getattr(args, "n", 20), console
                )
            if arena_cmd == "show":
                return _render_arena_show(getattr(args, "idea_id"), console)
            if arena_cmd == "post":
                return _render_arena_post(args, console)
            if arena_cmd == "comment":
                return _render_arena_comment(args, console)
            if arena_cmd == "bet":
                return _render_arena_bet(args, console)
            if arena_cmd == "trade":
                return _render_arena_trade(args, console)
            if arena_cmd == "positions":
                return _render_arena_positions(args, console)
            if arena_cmd == "stats":
                return _render_arena_stats(args, console)
            if arena_cmd == "exit":
                return _render_arena_exit(args, console)
            if arena_cmd == "resolve":
                return _render_arena_resolve(args, console)
            if arena_cmd == "ledger":
                return _render_arena_ledger(args, console)
            if arena_cmd == "rescue":
                return _render_arena_rescue(args, console)
            if arena_cmd == "borrow":
                return _render_arena_borrow(args, console)
            if arena_cmd == "repay":
                return _render_arena_repay(args, console)
            return _render_arena_ideas(False, 20, console)

        if cmd == "call":
            console.print(_call_panel(args, console))
            return 0

        if cmd == "all":
            from ..dashboard import render_call, render_intel, render_verdict
            from ..intel import gather
            from ..trade import make_idea

            candles, price, stats, fng, verdict = _gather_view(args)
            console.print(render_verdict(verdict, args.symbol, args.timeframe,
                                         price, stats, fng))
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
        console.print("\n[dim]fox went to sleep. \U0001f98a[/]")
        return 0
    except ArenaError as e:
        console.print(f"[bold red]arena error:[/] {e}")
        return 1
    except DataError as e:
        console.print(f"[bold red]data error:[/] {e}")
        return 1
