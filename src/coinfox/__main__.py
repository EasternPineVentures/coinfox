"""CLI entrypoint: `python -m coinfox`."""

from __future__ import annotations

import argparse
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .bias import get_bias
from .community.arena import ArenaError
from .credits import render_credits
from .dashboard import render_call, render_intel, render_verdict
from .data import DataError, fetch_24h_stats, fetch_fear_greed, fetch_klines, fetch_price
from .intel import gather
from .model import evaluate
from .new_source import scaffold
from .trade import make_idea
from .utils.json_utils import safe_json_dumps


def _add_pulse_subcommands(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("--explain", action="store_true",
                                help="explain pulse commands in plain English")
    pulse_sub = command_parser.add_subparsers(dest="pulse_cmd")

    status = pulse_sub.add_parser("status", help="provider health + latest AI read")
    status.add_argument("--benchmark", action="store_true",
                        help="run synthetic regime detector benchmark and exit")
    status.add_argument("--symbols", type=int, default=100,
                        help="number of synthetic symbols for --benchmark (default 100)")
    status.add_argument("--updates", type=int, default=500,
                        help="updates per symbol for --benchmark (default 500)")
    status.add_argument("--window-size", type=int, default=100,
                        help="regime window size for --benchmark (default 100)")
    status.add_argument("--json", action="store_true", help="print machine-readable JSON")
    status.add_argument("--explain", action="store_true", help="explain this command")

    tick = pulse_sub.add_parser("tick", help="force one AI pulse cycle right now (blocking)")
    tick.add_argument("--explain", action="store_true", help="explain this command")

    hist = pulse_sub.add_parser("history", help="show last N AI reads (drift view)")
    hist.add_argument("-n", type=int, default=10, help="how many reads to show (default 10)")
    hist.add_argument("--explain", action="store_true", help="explain this command")

    metrics = pulse_sub.add_parser("metrics", help="online accuracy/calibration report")
    metrics.add_argument("--window", type=int, default=200,
                         help="max reads to evaluate (default 200)")
    metrics.add_argument("--horizon-steps", type=int, default=6,
                         help="lookahead measured in pulse cycles (default 6)")
    metrics.add_argument("--neutral-band-pct", type=float, default=0.20,
                         help="absolute %% move treated as neutral (default 0.20)")
    metrics.add_argument("--explain", action="store_true", help="explain this command")

    replay = pulse_sub.add_parser("replay", help="replay pulse history through a quality gate")
    replay.add_argument("--synthetic", action="store_true",
                        help="use deterministic synthetic reads for CI/offline checks")
    replay.add_argument("--db", default=None, help="path to pulse sqlite database")
    replay.add_argument("--window", type=int, default=500,
                        help="max reads to replay (default 500)")
    replay.add_argument("--horizon-steps", type=int, default=6,
                        help="lookahead measured in pulse cycles (default 6)")
    replay.add_argument("--neutral-band-pct", type=float, default=0.20,
                        help="absolute %% move treated as neutral (default 0.20)")
    replay.add_argument("--min-sample-size", type=int, default=30,
                        help="minimum replay samples required to pass (default 30)")
    replay.add_argument("--min-hit-rate", type=float, default=0.55,
                        help="minimum hit rate required to pass (default 0.55)")
    replay.add_argument("--max-brier", type=float, default=0.35,
                        help="maximum brier-like score allowed to pass (default 0.35)")
    replay.add_argument("--explain", action="store_true", help="explain this command")

    tune = pulse_sub.add_parser("tune-regime", help="tune regime detector thresholds on deterministic cases")
    tune.add_argument("--explain", action="store_true", help="explain this command")

    feedback = pulse_sub.add_parser("feedback-report", help="summarize anonymous feedback events")
    feedback.add_argument("--symbol", help="filter report to one symbol")
    feedback.add_argument("--db", default=None, help="path to feedback sqlite database")
    feedback.add_argument("--limit", type=int, default=1000, help="max feedback events to inspect")
    feedback.add_argument("--json", action="store_true", help="print machine-readable JSON")
    feedback.add_argument("--explain", action="store_true", help="explain this command")

    run = pulse_sub.add_parser("run", help="always-on pulse with live status and countdown")
    run.add_argument("--interval", type=int, default=300,
                     help="seconds between pulse cycles (default 300)")
    run.add_argument("--explain", action="store_true", help="explain this command")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="coinfox",
        description=(
            "CoinFox - free, keyless market intelligence from Eastern Pine Intelligence, "
            "an open-source lab from Eastern Pine Ventures."
        ),
    )
    sub = p.add_subparsers(dest="cmd")

    # `watch` (also the default if no subcommand given)
    w = sub.add_parser("watch", help="signals + probability verdict (default)")
    _watch_args(w)

    # `bias`
    b = sub.add_parser("bias", help="CoinFox LONG/SHORT/NEUTRAL read")
    _watch_args(b)
    b.add_argument("--json", action="store_true", help="print machine-readable JSON")

    # `intel`
    i = sub.add_parser("intel", help="full firehose of BTC info from many sources")
    i.add_argument("--no-news", action="store_true")
    i.add_argument("--no-social", action="store_true")

    # `call`
    c = sub.add_parser("call", help="educational setup map: entry, risk area, target, size")
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

    api = sub.add_parser("api", help="run the CoinFox HTTP API")
    api.add_argument("--host", default="127.0.0.1", help="host to bind (default 127.0.0.1)")
    api.add_argument("--port", type=int, default=8000, help="port to bind (default 8000)")
    api.add_argument("--reload", action="store_true", help="reload when source files change")

    # `pulse` - AI context background commands.
    pulse = sub.add_parser("pulse", help="AI market pulse: status, tick, history, run")
    _add_pulse_subcommands(pulse)

    arena = sub.add_parser("arena", help="CoinFox arena: ideas, discussion, bets, leaderboard")
    arena_sub = arena.add_subparsers(dest="arena_cmd")

    whoami = arena_sub.add_parser("whoami", help="show or set your local arena handle")
    whoami.add_argument("--user", help="set your local arena handle")

    balance = arena_sub.add_parser("balance", help="show your FC balance")
    balance.add_argument("--user", help="override the local arena handle")

    profile = arena_sub.add_parser("profile", help="show or update an arena profile")
    profile.add_argument("--user", help="override the local arena handle")
    profile.add_argument("--display-name", help="set the public display name")
    profile.add_argument("--bio", help="set the public bio")

    say = arena_sub.add_parser("say", help="publish a social post to your profile and the shared feed")
    say.add_argument("--user", help="override the local arena handle")
    say.add_argument("--body", required=True)

    posts = arena_sub.add_parser("posts", help="list social posts for one user or everyone")
    posts.add_argument("--user", help="filter to one arena handle")
    posts.add_argument("-n", type=int, default=20, help="how many posts to show (default 20)")

    feed = arena_sub.add_parser("feed", help="show the shared arena feed")
    feed.add_argument("--user", help="filter to one arena handle")
    feed.add_argument("-n", type=int, default=20, help="how many events to show (default 20)")

    leaderboard = arena_sub.add_parser("leaderboard", help="top FC holders")
    leaderboard.add_argument("-n", type=int, default=10, help="how many users to show (default 10)")

    ideas = arena_sub.add_parser("ideas", help="list arena ideas")
    ideas.add_argument("--all", action="store_true", help="include resolved ideas")
    ideas.add_argument("-n", type=int, default=20, help="how many ideas to show (default 20)")

    show = arena_sub.add_parser("show", help="show one idea with comments and pools")
    show.add_argument("idea_id", type=int)

    post = arena_sub.add_parser("post", help="post a new trade idea")
    post.add_argument("--user", help="override the local arena handle")
    post.add_argument("--title", required=True)
    post.add_argument("--body", required=True)
    post.add_argument("--symbol", default="BTCUSDT")
    post.add_argument("--bias", default="long", choices=["long", "short", "neutral"])
    post.add_argument("--rule", required=True, help="explicit settlement rule")
    post.add_argument("--hours", type=int, default=24,
                      help="betting window in hours before the idea closes (default 24)")

    comment = arena_sub.add_parser("comment", help="add a comment to an arena idea")
    comment.add_argument("idea_id", type=int)
    comment.add_argument("--user", help="override the local arena handle")
    comment.add_argument("--body", required=True)

    bet = arena_sub.add_parser("bet", help="stake FC on an idea outcome")
    bet.add_argument("idea_id", type=int)
    bet.add_argument("--user", help="override the local arena handle")
    bet.add_argument("--amount", type=int, required=True)
    bet.add_argument("--direction", required=True, choices=["long", "short", "neutral"])

    market = arena_sub.add_parser("market", help="show New York Fox Exchange trading hours and rules")

    trade = arena_sub.add_parser("trade", help="open a NY Fox Exchange spot-style position during market hours")
    trade.add_argument("--user", help="override the local arena handle")
    trade.add_argument("--symbol", default="BTCUSDT")
    trade.add_argument("--direction", required=True, choices=["long", "short"])
    trade.add_argument("--amount", type=int, required=True)

    positions = arena_sub.add_parser("positions", help="show your NY Fox Exchange positions")
    positions.add_argument("--user", help="override the local arena handle")
    positions.add_argument("--all", action="store_true", help="include closed positions")
    positions.add_argument("-n", type=int, default=20, help="how many positions to show (default 20)")

    stats = arena_sub.add_parser("stats", help="show user stats or the top arena performers")
    stats.add_argument("--user", help="override the local arena handle")
    stats.add_argument("--leaderboard", action="store_true", help="show the stats leaderboard instead of one user")
    stats.add_argument("-n", type=int, default=10, help="how many leaderboard rows to show (default 10)")

    exit_trade = arena_sub.add_parser("exit", help="close an open NY Fox Exchange position during market hours")
    exit_trade.add_argument("position_id", type=int)
    exit_trade.add_argument("--user", help="override the local arena handle")

    resolve = arena_sub.add_parser("resolve", help="resolve an idea and settle bets")
    resolve.add_argument("idea_id", type=int)
    resolve.add_argument("--user", help="override the local arena handle")
    resolve.add_argument("--outcome", required=True, choices=["long", "short", "neutral"])

    ledger = arena_sub.add_parser("ledger", help="show recent FC ledger events")
    ledger.add_argument("--user", help="override the local arena handle")
    ledger.add_argument("-n", type=int, default=20, help="how many entries to show (default 20)")

    rescue = arena_sub.add_parser("rescue", help="rare bankruptcy rescue for users at 0 FC")
    rescue.add_argument("--user", help="override the local arena handle")

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


def _age_text(ts: int) -> str:
    age_s = max(0, int(time.time()) - int(ts))
    if age_s < 3600:
        return f"{age_s // 60}m ago"
    if age_s < 86400:
        return f"{age_s // 3600}h ago"
    return f"{age_s // 86400}d ago"


def _resolve_arena_user(arena, explicit_user: str | None) -> str:
    if explicit_user:
        return arena.ensure_user(explicit_user).handle
    handle = arena.identity()
    if not handle:
        raise ArenaError("no arena identity set; run `coinfox arena whoami --user yourname` first")
    return arena.ensure_user(handle).handle


def _render_arena_whoami(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    if getattr(args, "user", None):
        user = arena.set_identity(args.user)
        t = Table.grid(padding=(0, 2))
        t.add_column(style="dim")
        t.add_column()
        t.add_row("handle", user.handle)
        t.add_row("balance", f"{user.balance_fc} FC")
        t.add_row("identity file", "~/.coinfox/identity")
        console.print(Panel(t, title="arena identity", border_style="cyan"))
        return 0

    handle = arena.identity()
    if not handle:
        console.print("[yellow]No local arena handle yet.[/] Run [cyan]coinfox arena whoami --user yourname[/].")
        return 1
    user = arena.ensure_user(handle)
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("handle", user.handle)
    t.add_row("balance", f"{user.balance_fc} FC")
    console.print(Panel(t, title="arena identity", border_style="cyan"))
    return 0


def _render_arena_balance(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    user = arena.ensure_user(handle)
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("user", user.handle)
    t.add_row("balance", f"{user.balance_fc} FC")
    t.add_row("starting grant", "500 FC once")
    t.add_row("reset policy", "no reset; rescue only at 0 FC")
    t.add_row("NYFE sizing", "no leverage, no platform cap, max loss is your stake")
    console.print(Panel(t, title="FC balance", border_style="green"))
    return 0


def _render_arena_profile(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    if getattr(args, "display_name", None) is not None or getattr(args, "bio", None) is not None:
        profile = arena.update_profile(
            handle,
            display_name=getattr(args, "display_name", None),
            bio=getattr(args, "bio", None),
        )
    else:
        profile = arena.get_profile(handle)
    stats = arena.user_stats(handle)
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("handle", profile.handle)
    t.add_row("display name", profile.display_name)
    t.add_row("bio", profile.bio or "-")
    t.add_row("balance", f"{stats.balance_fc} FC")
    t.add_row("realized pnl", f"{stats.realized_pnl_fc:+d} FC")
    t.add_row("unrealized pnl", f"{stats.unrealized_pnl_fc:+d} FC")
    t.add_row("posts", str(len(arena.list_posts(handle=handle, limit=100))))
    console.print(Panel(t, title="arena profile", border_style="cyan"))
    return 0


def _render_arena_say(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    post = arena.create_post(handle, args.body)
    console.print(f"[bold green]posted:[/] social update #{post.id} by [cyan]{post.author_handle}[/]")
    return _render_arena_posts(getattr(args, "user", None), 5, console)


def _render_arena_posts(user: str | None, n: int, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    posts = arena.list_posts(handle=user, limit=max(1, int(n)))
    if not posts:
        console.print("[dim]No social posts yet. Publish one with [cyan]coinfox arena say --body \"...\"[/].[/]")
        return 0
    t = Table(title="Arena posts", expand=True)
    t.add_column("when", style="dim")
    t.add_column("user", style="cyan")
    t.add_column("post")
    for post in posts:
        t.add_row(_age_text(post.created_ts), post.author_handle, post.body)
    console.print(t)
    return 0


def _render_arena_feed(user: str | None, n: int, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    events = arena.feed(limit=max(1, int(n)), handle=user)
    if not events:
        console.print("[dim]No feed events yet. Start with a post, idea, or trade.[/]")
        return 0
    t = Table(title="Arena feed", expand=True)
    t.add_column("when", style="dim")
    t.add_column("type", style="dim")
    t.add_column("who", style="cyan")
    t.add_column("headline")
    t.add_column("detail")
    for event in events:
        t.add_row(
            _age_text(event.created_ts),
            event.event_type,
            event.handle or "system",
            event.headline,
            event.body,
        )
    console.print(t)
    return 0


def _format_session_time(ts: int) -> str:
    stamp = time.localtime(ts)
    return time.strftime("%Y-%m-%d %H:%M:%S", stamp)


def _render_arena_market(console: Console) -> int:
    from .community.arena import Arena, format_market_timestamp, market_now_text

    arena = Arena()
    session = arena.market_session()
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("exchange", "New York Fox Exchange")
    t.add_row("now", market_now_text())
    t.add_row("hours", "Mon-Fri 9:30 AM to 4:00 PM America/New_York")
    t.add_row("status", Text("OPEN" if session.is_open else "closed", style="green" if session.is_open else "red"))
    if session.is_open:
        t.add_row("closes", format_market_timestamp(session.closes_at_ts))
    else:
        t.add_row("next open", format_market_timestamp(session.opens_at_ts))
    t.add_row("structure", "spot-style only; no leverage")
    t.add_row("sizing", "no platform limit; if you nuke your stack, that is on you")
    t.add_row("exit rule", "you can sell anytime while NYFE is open")
    console.print(Panel(t, title="NY Fox Exchange", border_style="bright_blue"))
    console.print("[dim]Shorts are simulated with cash collateral only. Max loss is your stake. This is for fun, but users should still understand sizing matters.[/]")
    return 0


def _render_arena_leaderboard(n: int, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    users = arena.leaderboard(limit=max(1, int(n)))
    if not users:
        console.print("[dim]No arena users yet. Set one with [cyan]coinfox arena whoami --user yourname[/].[/]")
        return 0
    t = Table(title="CoinFox leaderboard", expand=True)
    t.add_column("rank", justify="right")
    t.add_column("user", style="cyan")
    t.add_column("balance", justify="right")
    t.add_column("joined", style="dim")
    for index, user in enumerate(users, start=1):
        t.add_row(str(index), user.handle, f"{user.balance_fc} FC", _age_text(user.created_ts))
    console.print(t)
    return 0


def _render_arena_ideas(show_all: bool, n: int, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    ideas = arena.list_ideas(status=None if show_all else "open", limit=max(1, int(n)))
    if not ideas:
        console.print("[dim]No arena ideas yet. Post one with [cyan]coinfox arena post[/].[/]")
        return 0
    t = Table(title="CoinFox arena ideas", expand=True)
    t.add_column("id", justify="right")
    t.add_column("symbol", style="dim")
    t.add_column("bias", justify="center")
    t.add_column("title")
    t.add_column("author", style="cyan")
    t.add_column("pool", justify="right")
    t.add_column("status", justify="center")
    for idea in ideas:
        pool = sum(bet.amount_fc for bet in arena.bets_for_idea(idea.id))
        t.add_row(
            str(idea.id),
            idea.symbol,
            Text(idea.bias.upper(), style=_bias_color(idea.bias)),
            idea.title,
            idea.author_handle,
            f"{pool} FC",
            idea.status,
        )
    console.print(t)
    return 0


def _render_arena_show(idea_id: int, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    idea = arena.get_idea(idea_id)
    if idea is None:
        console.print(f"[bold red]arena error:[/] idea {idea_id} does not exist")
        return 1

    header = Table.grid(padding=(0, 2))
    header.add_column(style="dim")
    header.add_column()
    header.add_row("idea", f"#{idea.id} {idea.title}")
    header.add_row("author", idea.author_handle)
    header.add_row("symbol", idea.symbol)
    header.add_row("bias", Text(idea.bias.upper(), style=_bias_color(idea.bias)))
    header.add_row("status", idea.status)
    header.add_row("opened", _age_text(idea.created_ts))
    if idea.closes_ts is not None:
        header.add_row("closes", _age_text(idea.closes_ts) if idea.closes_ts <= int(time.time()) else f"in {max(0, int(idea.closes_ts - time.time())) // 3600}h")
    if idea.outcome:
        header.add_row("outcome", Text(idea.outcome.upper(), style=_bias_color(idea.outcome)))

    console.print(Panel(header, title="arena idea", border_style=_bias_color(idea.bias)))
    console.print(Panel(Text(idea.body), title="thesis", border_style="dim"))
    console.print(Panel(Text(idea.resolution_rule, style="dim"), title="resolution rule", border_style="dim"))

    bets = arena.bets_for_idea(idea.id)
    pools = {"long": 0, "short": 0, "neutral": 0}
    for bet in bets:
        pools[bet.direction] = pools.get(bet.direction, 0) + bet.amount_fc
    pool_table = Table(title="bet pools", expand=True)
    pool_table.add_column("side", style="dim")
    pool_table.add_column("staked", justify="right")
    for side in ("long", "short", "neutral"):
        pool_table.add_row(side, f"{pools.get(side, 0)} FC")
    console.print(pool_table)

    comments = arena.comments(idea.id, limit=50)
    if comments:
        comment_table = Table(title="discussion", expand=True)
        comment_table.add_column("when", style="dim")
        comment_table.add_column("user", style="cyan")
        comment_table.add_column("comment")
        for comment in comments[-10:]:
            comment_table.add_row(_age_text(comment.created_ts), comment.author_handle, comment.body)
        console.print(comment_table)
    else:
        console.print("[dim]No comments yet. Add one with [cyan]coinfox arena comment[/].[/]")
    return 0


def _render_arena_post(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    hours = max(1, int(getattr(args, "hours", 24)))
    closes_ts = int(time.time()) + hours * 3600
    idea = arena.create_idea(
        author_handle=handle,
        title=args.title,
        body=args.body,
        symbol=args.symbol,
        bias=args.bias,
        resolution_rule=args.rule,
        closes_ts=closes_ts,
    )
    console.print(f"[bold green]posted:[/] idea #{idea.id} by [cyan]{idea.author_handle}[/]")
    return _render_arena_show(idea.id, console)


def _render_arena_comment(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    comment = arena.add_comment(args.idea_id, handle, args.body)
    console.print(f"[bold green]comment added:[/] #{comment.id} on idea {comment.idea_id}")
    return _render_arena_show(args.idea_id, console)


def _render_arena_bet(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    bet = arena.place_bet(args.idea_id, handle, args.direction, args.amount)
    balance = arena.balance(handle)
    console.print(
        f"[bold green]bet placed:[/] {bet.amount_fc} FC on [bold]{bet.direction.upper()}[/] for idea {bet.idea_id}. "
        f"Balance: [cyan]{balance} FC[/]."
    )
    return _render_arena_show(args.idea_id, console)


def _render_arena_trade(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    position = arena.open_position(handle, args.symbol, args.direction, args.amount)
    balance = arena.balance(handle)
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("position", f"#{position.id}")
    t.add_row("symbol", position.symbol)
    t.add_row("direction", Text(position.direction.upper(), style=_bias_color(position.direction)))
    t.add_row("stake", f"{position.amount_fc} FC")
    t.add_row("entry", f"{position.entry_price:.2f}")
    t.add_row("balance left", f"{balance} FC")
    console.print(Panel(t, title="NYFE position opened", border_style=_bias_color(position.direction)))
    console.print("[dim]No leverage. No platform bet cap. If you over-size, the fox will not save you.[/]")
    return 0


def _render_arena_positions(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    status = None if getattr(args, "all", False) else "open"
    marks = arena.marked_positions(handle=handle, status=status, limit=max(1, int(getattr(args, "n", 20))))
    if not marks:
        console.print("[dim]No positions found for this view.[/]")
        return 0
    t = Table(title=f"{handle} NY Fox Exchange positions", expand=True)
    t.add_column("id", justify="right")
    t.add_column("symbol", style="dim")
    t.add_column("side", justify="center")
    t.add_column("stake", justify="right")
    t.add_column("entry", justify="right")
    t.add_column("mark", justify="right")
    t.add_column("pnl", justify="right")
    t.add_column("status", justify="center")
    for mark in marks:
        position = mark.position
        pnl = position.realized_pnl_fc if position.status == "closed" else mark.unrealized_pnl_fc
        pnl_text = "n/a" if pnl is None else (f"+{pnl}" if pnl > 0 else str(pnl))
        pnl_style = "green" if pnl and pnl > 0 else "red" if pnl and pnl < 0 else "dim"
        marked_price = "n/a"
        if mark.current_price is not None:
            marked_price = f"{mark.current_price:.2f}"
        t.add_row(
            str(position.id),
            position.symbol,
            Text(position.direction.upper(), style=_bias_color(position.direction)),
            f"{position.amount_fc} FC",
            f"{position.entry_price:.2f}",
            marked_price,
            Text(pnl_text, style=pnl_style),
            position.status,
        )
    console.print(t)
    return 0


def _render_arena_stats(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    if getattr(args, "leaderboard", False):
        rows = arena.stats_leaderboard(limit=max(1, int(getattr(args, "n", 10))))
        if not rows:
            console.print("[dim]No arena users yet. Set one with [cyan]coinfox arena whoami --user yourname[/].[/]")
            return 0
        t = Table(title="Arena performance leaderboard", expand=True)
        t.add_column("rank", justify="right")
        t.add_column("user", style="cyan")
        t.add_column("realized", justify="right")
        t.add_column("unrealized", justify="right")
        t.add_column("wins", justify="right")
        t.add_column("losses", justify="right")
        t.add_column("balance", justify="right")
        for index, stat in enumerate(rows, start=1):
            realized = f"+{stat.realized_pnl_fc}" if stat.realized_pnl_fc > 0 else str(stat.realized_pnl_fc)
            unrealized = f"+{stat.unrealized_pnl_fc}" if stat.unrealized_pnl_fc > 0 else str(stat.unrealized_pnl_fc)
            t.add_row(
                str(index),
                stat.handle,
                realized,
                unrealized,
                str(stat.winning_positions),
                str(stat.losing_positions),
                f"{stat.balance_fc} FC",
            )
        console.print(t)
        return 0

    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    stat = arena.user_stats(handle)
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("user", stat.handle)
    t.add_row("balance", f"{stat.balance_fc} FC")
    t.add_row("open positions", str(stat.open_positions))
    t.add_row("closed positions", str(stat.closed_positions))
    t.add_row("wins", str(stat.winning_positions))
    t.add_row("losses", str(stat.losing_positions))
    t.add_row("realized pnl", f"{stat.realized_pnl_fc:+d} FC")
    t.add_row("unrealized pnl", f"{stat.unrealized_pnl_fc:+d} FC")
    t.add_row("total staked", f"{stat.total_staked_fc} FC")
    console.print(Panel(t, title="arena stats", border_style="magenta"))
    return 0


def _render_arena_exit(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    position = arena.close_position(args.position_id, handle)
    balance = arena.balance(handle)
    pnl = position.realized_pnl_fc
    pnl_text = f"+{pnl}" if pnl > 0 else str(pnl)
    pnl_style = "green" if pnl > 0 else "red" if pnl < 0 else "yellow"
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("position", f"#{position.id}")
    t.add_row("symbol", position.symbol)
    t.add_row("exit", f"{position.exit_price:.2f}" if position.exit_price is not None else "n/a")
    t.add_row("pnl", Text(pnl_text + " FC", style=pnl_style))
    t.add_row("balance", f"{balance} FC")
    console.print(Panel(t, title="NYFE position closed", border_style=pnl_style))
    return 0


def _render_arena_resolve(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    idea = arena.resolve_idea(args.idea_id, args.outcome, handle)
    console.print(
        f"[bold green]resolved:[/] idea {idea.id} -> "
        f"[bold]{idea.outcome.upper() if idea.outcome else 'UNKNOWN'}[/]"
    )
    return _render_arena_show(args.idea_id, console)


def _render_arena_ledger(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    rows = arena.ledger(handle, limit=max(1, int(getattr(args, "n", 20))))
    if not rows:
        console.print("[dim]No FC ledger entries yet.[/]")
        return 0
    t = Table(title=f"{handle} FC ledger", expand=True)
    t.add_column("when", style="dim")
    t.add_column("delta", justify="right")
    t.add_column("reason")
    t.add_column("ref", style="dim")
    for row in rows:
        ref = "-"
        if row["ref_kind"] and row["ref_id"] is not None:
            ref = f"{row['ref_kind']}:{row['ref_id']}"
        delta = int(row["delta_fc"])
        delta_text = f"+{delta}" if delta > 0 else str(delta)
        style = "green" if delta > 0 else "red"
        t.add_row(_age_text(int(row["created_ts"])), Text(delta_text, style=style), str(row["reason"]), ref)
    console.print(t)
    return 0


def _render_arena_rescue(args, console: Console) -> int:
    from .community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    user = arena.rescue(handle)
    console.print(
        f"[bold green]bankruptcy rescue granted:[/] [cyan]{user.handle}[/] now has {user.balance_fc} FC."
    )
    return _render_arena_balance(args, console)


def _render_churn_status(args, console: Console) -> int:
    from .ai.churn import ChurnDaemon
    from .ai.router import FoxClaw
    from .ai.regime import run_regime_benchmark

    if getattr(args, "benchmark", False):
        bench = run_regime_benchmark(
            symbols=getattr(args, "symbols", 100),
            updates_per_symbol=getattr(args, "updates", 500),
            window_size=getattr(args, "window_size", 100),
        )
        if getattr(args, "json", False):
            print(safe_json_dumps(bench, indent=2, sort_keys=True))
            return 0
        bt = Table(title="Regime detector benchmark", expand=True)
        bt.add_column("metric", style="dim")
        bt.add_column("value")
        bt.add_row("symbols", str(bench.get("symbols")))
        bt.add_row("updates/symbol", str(bench.get("updates_per_symbol")))
        bt.add_row("total updates", str(bench.get("total_updates")))
        bt.add_row("elapsed", f"{bench.get('elapsed_s', 0.0)}s")
        bt.add_row("throughput", f"{bench.get('updates_per_s', 0.0)} updates/s")
        bt.add_row("latency", f"{bench.get('us_per_update', 0.0)} us/update")
        bt.add_row("sample regime", str(bench.get("sample_regime", "n/a")))
        console.print(bt)
        return 0

    daemon = ChurnDaemon()
    fox = FoxClaw()
    status = fox.status()
    configured = fox.configured_provider_names()
    thought = daemon.latest()
    digest = daemon.latest_digest() or {}
    health = daemon.health()

    if getattr(args, "json", False):
        payload = {
            "provider_routing": {
                "configured_providers": configured,
                "override": "COINFOX_AI_PROVIDERS=ollama,groq,gemini",
            },
            "providers": status,
            "watchdog_health": health,
            "latest_digest": digest,
            "latest_thought": (
                {
                    "ts": thought.ts,
                    "bias": thought.bias,
                    "conviction": thought.conviction,
                    "headline": thought.headline,
                    "body": thought.body,
                    "provider": thought.provider,
                    "model": thought.model,
                    "cost_tier": thought.cost_tier,
                }
                if thought
                else None
            ),
        }
        print(safe_json_dumps(payload, indent=2, sort_keys=True))
        return 0

    cfg = Table.grid(padding=(0, 2))
    cfg.add_column(style="dim")
    cfg.add_column()
    cfg.add_row("configured providers", ", ".join(configured) if configured else "none")
    cfg.add_row("override", "COINFOX_AI_PROVIDERS=ollama,groq,gemini")
    console.print(Panel(cfg, title="provider routing", border_style="dim"))

    t = Table(title="AI context provider status", expand=True)
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

    ht = Table.grid(padding=(0, 2))
    ht.add_column(style="dim")
    ht.add_column()
    ht.add_row("phase", str(health.get("phase") or "unknown"))
    hb_age = health.get("heartbeat_age_s")
    ht.add_row("heartbeat age", "n/a" if hb_age is None else f"{int(hb_age)}s")
    ht.add_row("stale", "YES" if health.get("stale") else "no")
    lo_age = health.get("last_ok_age_s")
    ht.add_row("last success age", "n/a" if lo_age is None else f"{int(lo_age)}s")
    if health.get("last_error"):
        ht.add_row("last error", str(health.get("last_error")))
    console.print(Panel(ht, title="watchdog health", border_style="dim"))

    learning = digest.get("learning") if isinstance(digest, dict) else None
    regime = digest.get("regime") if isinstance(digest, dict) else None
    source_rel = digest.get("source_reliability") if isinstance(digest, dict) else None
    if isinstance(learning, dict):
        lt = Table.grid(padding=(0, 2))
        lt.add_column(style="dim")
        lt.add_column()
        lt.add_row("strange market", "YES" if learning.get("strange_market") else "no")
        lt.add_row("anomaly score", str(learning.get("anomaly_score", 0.0)))
        lt.add_row("top feature", str(learning.get("top_feature") or "n/a"))
        lt.add_row("samples", str(learning.get("sample_size", 0)))
        console.print(Panel(lt, title="learning snapshot", border_style="dim"))

    if isinstance(source_rel, dict):
        st = Table.grid(padding=(0, 2))
        st.add_column(style="dim")
        st.add_column()
        st.add_row("overall reliability", f"{float(source_rel.get('overall', 0.0)) * 100:.1f}%")
        st.add_row("history samples", str(source_rel.get("sample_size", 0)))
        st.add_row("weakest source", str(source_rel.get("weakest_source") or "n/a"))
        current_errors = source_rel.get("current_errors")
        if isinstance(current_errors, list) and current_errors:
            st.add_row("current errors", ", ".join(str(x) for x in current_errors))
        console.print(Panel(st, title="source reliability", border_style="dim"))

    if isinstance(regime, dict):
        rt = Table.grid(padding=(0, 2))
        rt.add_column(style="dim")
        rt.add_column()
        rt.add_row("name", str(regime.get("name") or "unknown"))
        rt.add_row("confidence", f"{float(regime.get('confidence', 0.0)) * 100:.1f}%")
        metrics = regime.get("metrics")
        if isinstance(metrics, dict):
            rt.add_row("trend strength", f"{float(metrics.get('trend_strength', 0.0)):.3f}")
            rt.add_row("ewma vol", f"{float(metrics.get('ewma_vol', 0.0)):.5f}")
            rt.add_row("panic drop", f"{float(metrics.get('panic_drop_pct', 0.0)):.2f}%")
            rt.add_row("vol spike", f"{float(metrics.get('panic_volume_mult', 0.0)):.2f}x")
        console.print(Panel(rt, title="regime", border_style="dim"))

    if thought:
        age_s = int(time.time()) - thought.ts
        age_str = f"{age_s // 60}m {age_s % 60}s ago" if age_s < 3600 else f"{age_s // 3600}h ago"
        g = Table.grid(padding=(0, 2))
        g.add_column(style="dim")
        g.add_column()
        g.add_row("bias", Text(thought.bias.upper(), style=_bias_color(thought.bias)))
        g.add_row("conviction", f"{thought.conviction}/5")
        g.add_row("headline", thought.headline)
        g.add_row("provider", f"{thought.provider} ({thought.model})")
        g.add_row("age", age_str)
        console.print(Panel(g, title="last AI context read", border_style=_bias_color(thought.bias)))
        console.print(Panel(Text(thought.body, style="dim"),
                            title="reasoning", border_style="dim"))
    else:
        console.print("[dim]No AI context reads stored yet. Run [cyan]coinfox pulse tick[/] to generate one.[/]")
    return 0


def _render_churn_tick(console: Console) -> int:
    from .ai.churn import ChurnDaemon
    daemon = ChurnDaemon()
    console.print("[dim]Gathering intel and asking the AI context layer...[/]")
    start = time.time()
    thought = daemon.tick_once()
    elapsed = time.time() - start
    if not thought:
        console.print("[bold red]pulse failed:[/] no AI provider answered. "
                      "Install Ollama or set at least one API key env var. "
                      "Run [cyan]coinfox pulse status[/] to see available providers.")
        return 1
    g = Table.grid(padding=(0, 2))
    g.add_column(style="dim")
    g.add_column()
    g.add_row("bias", Text(thought.bias.upper(), style=_bias_color(thought.bias)))
    g.add_row("conviction", f"{thought.conviction}/5")
    g.add_row("headline", thought.headline)
    g.add_row("provider", f"{thought.provider} ({thought.model})")
    g.add_row("elapsed", f"{elapsed:.1f}s")
    console.print(Panel(g, title="AI context read", border_style=_bias_color(thought.bias)))
    console.print(Panel(Text(thought.body), title="reasoning", border_style="dim"))
    console.print("[dim]AI read stored in local pulse history[/]")
    return 0


def _render_churn_history(n: int, console: Console) -> int:
    from .ai.churn import ChurnDaemon
    daemon = ChurnDaemon()
    thoughts = daemon.recent(n)
    if not thoughts:
        console.print("[dim]No AI reads yet. Run [cyan]coinfox pulse tick[/] first.[/]")
        return 0
    t = Table(title=f"AI context history (last {len(thoughts)})", expand=True)
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


def _render_churn_metrics(window: int, horizon_steps: int, neutral_band_pct: float,
                          console: Console) -> int:
    from .ai.churn import ChurnDaemon

    daemon = ChurnDaemon()
    r = daemon.accuracy_report(
        window=max(20, int(window)),
        horizon_steps=max(1, int(horizon_steps)),
        neutral_band_pct=float(neutral_band_pct),
    )
    t = Table(title="AI context online quality metrics", expand=True)
    t.add_column("metric", style="dim")
    t.add_column("value")
    t.add_row("sample size", str(r.get("sample_size", 0)))
    t.add_row("horizon (steps)", str(r.get("horizon_steps", horizon_steps)))
    t.add_row("hit rate", f"{float(r.get('hit_rate', 0.0)) * 100:.1f}%")
    t.add_row("weighted hit rate", f"{float(r.get('weighted_hit_rate', 0.0)) * 100:.1f}%")
    t.add_row("brier-like", f"{float(r.get('brier_like', 0.0)):.4f}")
    t.add_row("strange-market rate", f"{float(r.get('strange_rate', 0.0)) * 100:.1f}%")
    console.print(t)
    console.print("[dim]Note: this is online directional scoring from stored thought history, not a guarantee.[/]")
    return 0


def _render_churn_replay(args, console: Console) -> int:
    from pathlib import Path

    from .ai.replay import run_replay_quality_gate

    db_arg = getattr(args, "db", None)
    result = run_replay_quality_gate(
        db_path=Path(db_arg) if db_arg else None,
        synthetic=getattr(args, "synthetic", False),
        window=getattr(args, "window", 500),
        horizon_steps=getattr(args, "horizon_steps", 6),
        neutral_band_pct=getattr(args, "neutral_band_pct", 0.20),
        min_sample_size=getattr(args, "min_sample_size", 30),
        min_hit_rate=getattr(args, "min_hit_rate", 0.55),
        max_brier_like=getattr(args, "max_brier", 0.35),
    )
    report = result.get("report", {})
    thresholds = result.get("thresholds", {})

    status = Text("PASS", style="bold green") if result.get("passed") else Text("FAIL", style="bold red")
    t = Table(title="Pulse replay quality gate", expand=True)
    t.add_column("metric", style="dim")
    t.add_column("value")
    t.add_row("status", status)
    t.add_row("source", str(result.get("source", "unknown")))
    t.add_row("sample size", str(report.get("sample_size", 0)))
    t.add_row("horizon (steps)", str(report.get("horizon_steps", getattr(args, "horizon_steps", 6))))
    t.add_row("hit rate", f"{float(report.get('hit_rate', 0.0)) * 100:.1f}%")
    t.add_row("weighted hit rate", f"{float(report.get('weighted_hit_rate', 0.0)) * 100:.1f}%")
    t.add_row("brier-like", f"{float(report.get('brier_like', 0.0)):.4f}")
    t.add_row("min sample", str(thresholds.get("min_sample_size", 0)))
    t.add_row("min hit rate", f"{float(thresholds.get('min_hit_rate', 0.0)) * 100:.1f}%")
    t.add_row("max brier-like", f"{float(thresholds.get('max_brier_like', 0.0)):.4f}")
    console.print(t)

    checks = result.get("checks", {})
    ct = Table(title="Gate checks", expand=True)
    ct.add_column("check", style="dim")
    ct.add_column("result")
    for name in ("sample_size", "hit_rate", "brier_like"):
        ok = bool(checks.get(name))
        ct.add_row(name, Text("ok" if ok else "fail", style="green" if ok else "red"))
    console.print(ct)
    return 0 if result.get("passed") else 1


def _render_churn_tune_regime(console: Console) -> int:
    from .ai.regime import tune_regime_thresholds

    result = tune_regime_thresholds()
    baseline = result.get("baseline", {})
    best = result.get("best", {})
    cfg = result.get("recommended_config", {})

    t = Table(title="Regime threshold tuner", expand=True)
    t.add_column("metric", style="dim")
    t.add_column("baseline")
    t.add_column("best")
    t.add_row("accuracy", f"{float(baseline.get('accuracy', 0.0)) * 100:.1f}%",
              f"{float(best.get('accuracy', 0.0)) * 100:.1f}%")
    t.add_row("mean confidence", f"{float(baseline.get('mean_confidence', 0.0)) * 100:.1f}%",
              f"{float(best.get('mean_confidence', 0.0)) * 100:.1f}%")
    t.add_row("sample size", str(baseline.get("sample_size", 0)), str(best.get("sample_size", 0)))
    t.add_row("improved", "", "YES" if result.get("improved") else "no")
    console.print(t)

    ct = Table(title="Recommended thresholds", expand=True)
    ct.add_column("setting", style="dim")
    ct.add_column("value")
    for key in (
        "trend_strength_threshold",
        "chop_threshold",
        "panic_price_drop_pct",
        "panic_volume_mult",
        "squeeze_volatility_pct",
    ):
        ct.add_row(key, str(cfg.get(key)))
    console.print(ct)
    return 0


def _render_pulse_explain(command: str, console: Console) -> int:
    explanations = {
        "status": (
            "Pulse status shows provider routing, watchdog health, source reliability, "
            "regime context, and the latest CoinFox market read. Beginners should look "
            "for stale health, missing sources, and whether confidence is strong or mixed."
        ),
        "tick": (
            "Pulse tick forces one market-read cycle now. It gathers public data, asks "
            "the AI context layer for a read, and stores the result locally."
        ),
        "history": (
            "Pulse history shows recent stored reads so you can see drift over time. "
            "Beginners should watch for frequent flips between LONG, SHORT, and NEUTRAL."
        ),
        "metrics": (
            "Pulse metrics scores stored reads against later price movement. Look at "
            "sample size, hit rate, weighted hit rate, and brier-like calibration."
        ),
        "replay": (
            "Pulse replay runs historical or synthetic reads through a quality gate. "
            "A pass means the check met its configured thresholds; it is not a promise "
            "about future market behavior."
        ),
        "tune-regime": (
            "Pulse tune-regime adjusts deterministic regime thresholds. Compare baseline "
            "and best results, then review the recommended config before using it."
        ),
        "feedback-report": (
            "Pulse feedback-report summarizes anonymous user feedback. It reports patterns "
            "for maintainers, such as disagreement counts and adjusted thesis-check levels. "
            "It does not automatically rewrite model behavior."
        ),
        "run": (
            "Pulse run starts the always-on market read loop with a live status panel. "
            "It is monitoring and logging context, not controlling a trading account."
        ),
    }
    text = explanations.get(command) or (
        "Pulse is CoinFox's always-on market read loop. It checks sources, gathers "
        "context, stores reads, and exposes health so the system stays auditable."
    )
    safety = (
        "Safety note: CoinFox is educational market intelligence. It does not place "
        "trades or know your personal risk."
    )
    console.print(Panel(Text(f"{text}\n\n{safety}"), title=f"pulse {command} --explain", border_style="cyan"))
    return 0


def _render_pulse_feedback_report(args, console: Console) -> int:
    from pathlib import Path

    from .feedback import build_feedback_report, format_feedback_report

    db_arg = getattr(args, "db", None)
    report = build_feedback_report(
        db_path=Path(db_arg) if db_arg else None,
        symbol=getattr(args, "symbol", None),
        limit=getattr(args, "limit", 1000),
    )
    payload = report.as_dict()
    if getattr(args, "json", False):
        print(safe_json_dumps(payload, indent=2, sort_keys=True))
        return 0
    console.print(Panel(format_feedback_report(report), title="Feedback learning report", border_style="cyan"))
    return 0


def _render_bias(args, console: Console) -> int:
    read = get_bias(
        symbol=getattr(args, "symbol", "BTCUSDT"),
        timeframe=getattr(args, "timeframe", "1h"),
        horizon=getattr(args, "horizon", 4),
        limit=getattr(args, "limit", 250),
        use_derivs=getattr(args, "use_derivs", False),
    )
    payload = read.as_dict()
    if getattr(args, "json", False):
        print(safe_json_dumps(payload, indent=2, sort_keys=True))
        return 0

    color = {"LONG": "bold green", "SHORT": "bold red", "NEUTRAL": "bold yellow"}.get(read.bias, "white")
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("symbol", read.symbol)
    t.add_row("bias", Text(read.bias, style=color))
    t.add_row("conviction", f"{read.conviction * 100:.1f}%")
    t.add_row("P(up)", f"{read.probability_up * 100:.1f}%")
    t.add_row("P(down)", f"{read.probability_down * 100:.1f}%")
    t.add_row("confidence", f"{read.confidence * 100:.1f}%")
    if read.price is not None:
        t.add_row("price", f"${read.price:,.2f}")
    if read.change_24h_pct is not None:
        t.add_row("24h", f"{read.change_24h_pct:+.2f}%")
    t.add_row("regime", read.regime_hint)
    if read.invalidation.level is not None:
        t.add_row("thesis check", f"{read.invalidation.type} ${read.invalidation.level:,.2f}")

    drivers = Table(title="top drivers", expand=True)
    drivers.add_column("signal", style="cyan")
    drivers.add_column("lean", justify="center")
    drivers.add_column("contrib", justify="right")
    drivers.add_column("detail", style="dim")
    for driver in read.drivers:
        lean = str(driver["lean"])
        lean_color = {"LONG": "green", "SHORT": "red", "NEUTRAL": "yellow"}.get(lean, "white")
        drivers.add_row(
            str(driver["name"]),
            Text(lean, style=lean_color),
            f"{float(driver['contribution']):+.2f}",
            str(driver["detail"]),
        )

    console.print(Panel(t, title="CoinFox bias", border_style=color))
    console.print(Panel(read.human_readable, title="read", border_style="dim"))
    console.print(drivers)
    return 0


def _render_churn_run(interval: int, console: Console) -> int:
    from rich.console import Group

    from .ai.churn import ChurnDaemon

    interval = max(15, int(interval))
    daemon = ChurnDaemon(interval_seconds=interval)
    cycle = 0
    phase = "booting"
    next_run_at = time.time()
    last_thought = daemon.latest()
    last_elapsed = 0.0
    last_error = None

    def _view() -> Panel:
        latest_digest = daemon.latest_digest() or {}
        learning = latest_digest.get("learning") if isinstance(latest_digest, dict) else None
        health = daemon.health(stale_after_s=max(60, interval * 2))

        top = Table.grid(padding=(0, 2))
        top.add_column(style="dim")
        top.add_column()
        top.add_row("mode", "always-on")
        top.add_row("interval", f"{interval}s")
        top.add_row("status", "running (Ctrl+C to stop)")

        runtime = Table.grid(padding=(0, 2))
        runtime.add_column(style="dim")
        runtime.add_column()
        runtime.add_row("cycle", str(cycle))
        runtime.add_row("phase", phase)
        runtime.add_row("next run", f"in {max(0, int(next_run_at - time.time()))}s")
        runtime.add_row("watchdog", "STALE" if health.get("stale") else "ok")
        hb_age = health.get("heartbeat_age_s")
        runtime.add_row("heartbeat age", "n/a" if hb_age is None else f"{int(hb_age)}s")

        if last_thought:
            runtime.add_row("last bias", Text(last_thought.bias.upper(), style=_bias_color(last_thought.bias)))
            runtime.add_row("conviction", f"{last_thought.conviction}/5")
            runtime.add_row("provider", f"{last_thought.provider} ({last_thought.model})")
            runtime.add_row("last run", f"{last_elapsed:.1f}s")
            runtime.add_row("headline", last_thought.headline)

        hint_style = "yellow" if last_error else "dim"
        hint = last_error or "This panel updates every second with what the AI loop is doing."
        body = [Panel(top, title="AI context", border_style="cyan"),
                Panel(runtime, title="runtime", border_style="green")]
        if isinstance(learning, dict):
            ltbl = Table.grid(padding=(0, 2))
            ltbl.add_column(style="dim")
            ltbl.add_column()
            ltbl.add_row("strange market", "YES" if learning.get("strange_market") else "no")
            ltbl.add_row("anomaly score", str(learning.get("anomaly_score", 0.0)))
            ltbl.add_row("top feature", str(learning.get("top_feature") or "n/a"))
            ltbl.add_row("sample size", str(learning.get("sample_size", 0)))
            body.append(Panel(ltbl, title="learning", border_style="magenta"))
        if last_thought:
            body.append(Panel(Text(last_thought.body, style="dim"), title="latest reasoning", border_style="dim"))
        body.append(Text(hint, style=hint_style))
        return Panel(Group(*body), title="🦊 coinfox pulse run", border_style="bright_blue")

    with Live(_view(), console=console, refresh_per_second=4, screen=False) as live:
        while True:
            now = time.time()
            if now >= next_run_at:
                cycle += 1
                phase = "gathering intel + asking AI context"
                live.update(_view())
                started = time.time()
                thought = daemon.tick_once()
                last_elapsed = time.time() - started
                if thought is None:
                    last_error = "No provider answered this cycle. Check keys with `coinfox pulse status`."
                    phase = "sleeping (last cycle failed)"
                else:
                    last_thought = thought
                    last_error = None
                    phase = "sleeping"
                next_run_at = time.time() + interval
            live.update(_view())
            time.sleep(1)


def _run_api_server(args, console: Console) -> int:
    try:
        import uvicorn
    except ImportError:
        console.print("[bold red]error:[/] install API dependencies with `pip install -e .[api]`")
        return 1

    host = getattr(args, "host", "127.0.0.1")
    port = int(getattr(args, "port", 8000))
    console.print(f"[green]Starting CoinFox API[/] at http://{host}:{port}")
    uvicorn.run("coinfox.api:app", host=host, port=port, reload=bool(getattr(args, "reload", False)))
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "churn":
        argv[0] = "pulse"
    args = _build_parser().parse_args(argv)
    console = Console()
    cmd = args.cmd or "watch"

    try:
        if cmd == "intel":
            intel = gather()
            console.print(render_intel(intel))
            return 0

        if cmd == "bias":
            return _render_bias(args, console)

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
                return _render_arena_posts(getattr(args, "user", None), getattr(args, "n", 20), console)
            if arena_cmd == "feed":
                return _render_arena_feed(getattr(args, "user", None), getattr(args, "n", 20), console)
            if arena_cmd == "market":
                return _render_arena_market(console)
            if arena_cmd == "leaderboard":
                return _render_arena_leaderboard(getattr(args, "n", 10), console)
            if arena_cmd == "ideas":
                return _render_arena_ideas(getattr(args, "all", False), getattr(args, "n", 20), console)
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
            return _render_arena_ideas(False, 20, console)

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
    except ArenaError as e:
        console.print(f"[bold red]arena error:[/] {e}")
        return 1
    except DataError as e:
        console.print(f"[bold red]data error:[/] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
