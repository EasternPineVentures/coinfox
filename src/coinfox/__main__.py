"""CLI entrypoint: `python -m coinfox`."""

from __future__ import annotations

import argparse
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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

    # `churn` — FoxClaw background-brain commands
    ch = sub.add_parser("churn", help="FoxClaw AI churn: status, tick, history")
    ch_sub = ch.add_subparsers(dest="churn_cmd")

    ch_sub.add_parser("status", help="provider health + last thought")
    ch_sub.add_parser("tick", help="force one AI churn cycle right now (blocking)")
    hist = ch_sub.add_parser("history", help="show last N AI thoughts (drift view)")
    hist.add_argument("-n", type=int, default=10, help="how many thoughts to show (default 10)")

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


def _bias_color(bias: str) -> str:
    return {"long": "bold green", "short": "bold red", "neutral": "bold yellow"}.get(bias, "white")


def _render_churn_status(console: Console) -> int:
    from .ai.churn import ChurnDaemon
    from .ai.router import FoxClaw
    daemon = ChurnDaemon()
    fox = FoxClaw()
    status = fox.status()

    t = Table(title="FoxClaw provider status", expand=True)
    t.add_column("provider", style="cyan")
    t.add_column("tier", style="dim")
    t.add_column("key env", style="dim")
    t.add_column("available", justify="center")
    t.add_column("ok", justify="right")
    t.add_column("fail", justify="right")
    t.add_column("model", style="dim")
    for p in status:
        avail = Text("YES", style="green") if p["available"] else Text("no", style="dim red")
        t.add_row(p["name"], p["tier"], p["key_env"] or "—", avail,
                  str(p["ok"]), str(p["fail"]), p["model"] or "—")
    console.print(t)

    thought = daemon.latest()
    if thought:
        age_s = int(time.time()) - thought.ts
        age_str = f"{age_s // 60}m {age_s % 60}s ago" if age_s < 3600 else f"{age_s // 3600}h ago"
        g = Table.grid(padding=(0, 2))
        g.add_column(style="dim"); g.add_column()
        g.add_row("bias", Text(thought.bias.upper(), style=_bias_color(thought.bias)))
        g.add_row("conviction", f"{thought.conviction}/5")
        g.add_row("headline", thought.headline)
        g.add_row("provider", f"{thought.provider} ({thought.model})")
        g.add_row("age", age_str)
        console.print(Panel(g, title="last FoxClaw thought", border_style=_bias_color(thought.bias)))
        console.print(Panel(Text(thought.body, style="dim"),
                            title="reasoning", border_style="dim"))
    else:
        console.print("[dim]No thoughts stored yet. Run [cyan]coinfox churn tick[/] to generate one.[/]")
    return 0


def _render_churn_tick(console: Console) -> int:
    from .ai.churn import ChurnDaemon
    daemon = ChurnDaemon()
    console.print("[dim]Gathering intel and asking FoxClaw...[/]")
    start = time.time()
    thought = daemon.tick_once()
    elapsed = time.time() - start
    if not thought:
        console.print("[bold red]churn failed:[/] no AI provider answered. "
                      "Install Ollama or set at least one API key env var. "
                      "Run [cyan]coinfox churn status[/] to see available providers.")
        return 1
    g = Table.grid(padding=(0, 2))
    g.add_column(style="dim"); g.add_column()
    g.add_row("bias", Text(thought.bias.upper(), style=_bias_color(thought.bias)))
    g.add_row("conviction", f"{thought.conviction}/5")
    g.add_row("headline", thought.headline)
    g.add_row("provider", f"{thought.provider} ({thought.model})")
    g.add_row("elapsed", f"{elapsed:.1f}s")
    console.print(Panel(g, title="FoxClaw thought", border_style=_bias_color(thought.bias)))
    console.print(Panel(Text(thought.body), title="reasoning", border_style="dim"))
    console.print("[dim]Thought stored in ~/.coinfox/churn.sqlite[/]")
    return 0


def _render_churn_history(n: int, console: Console) -> int:
    from .ai.churn import ChurnDaemon
    daemon = ChurnDaemon()
    thoughts = daemon.recent(n)
    if not thoughts:
        console.print("[dim]No thoughts yet. Run [cyan]coinfox churn tick[/] first.[/]")
        return 0
    t = Table(title=f"FoxClaw thought history (last {len(thoughts)})", expand=True)
    t.add_column("time", style="dim")
    t.add_column("bias", justify="center")
    t.add_column("conv", justify="center")
    t.add_column("headline")
    t.add_column("provider", style="dim")
    now = int(time.time())
    for th in thoughts:
        age_s = now - th.ts
        if age_s < 3600:
            age_str = f"{age_s // 60}m ago"
        elif age_s < 86400:
            age_str = f"{age_s // 3600}h ago"
        else:
            age_str = f"{age_s // 86400}d ago"
        t.add_row(age_str, Text(th.bias.upper(), style=_bias_color(th.bias)),
                  str(th.conviction), th.headline, th.provider)
    console.print(t)
    # bias drift summary
    biases = [th.bias for th in thoughts]
    long_c = biases.count("long")
    short_c = biases.count("short")
    neutral_c = biases.count("neutral")
    flips = sum(1 for i in range(1, len(biases)) if biases[i] != biases[i - 1])
    console.print(
        f"[dim]drift: [green]{long_c}L[/] / [red]{short_c}S[/] / [yellow]{neutral_c}N[/]"
        f"  flips: {flips}[/]"
    )
    return 0


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

        if cmd == "churn":
            churn_cmd = getattr(args, "churn_cmd", None) or "status"
            if churn_cmd == "status":
                return _render_churn_status(console)
            if churn_cmd == "tick":
                return _render_churn_tick(console)
            if churn_cmd == "history":
                return _render_churn_history(getattr(args, "n", 10), console)
            # fallback
            return _render_churn_status(console)

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
