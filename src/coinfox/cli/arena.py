"""Arena CLI render functions - all `_render_arena_*` handlers."""

from __future__ import annotations

import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ._shared import _age_text, _bias_color, _resolve_arena_user


def _render_arena_whoami(args, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    if getattr(args, "user", None):
        user = arena.set_identity(args.user)
        t = Table.grid(padding=(0, 2))
        t.add_column(style="dim")
        t.add_column()
        t.add_row("handle", user.handle)
        t.add_row("balance", f"{user.balance_fc} Gold (g)")
        t.add_row("identity file", "~/.coinfox/identity")
        console.print(Panel(t, title="arena identity", border_style="cyan"))
        return 0

    handle = arena.identity()
    if not handle:
        console.print(
            "[yellow]No local arena handle yet.[/] "
            "Run [cyan]coinfox arena whoami --user yourname[/]."
        )
        return 1
    user = arena.ensure_user(handle)
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("handle", user.handle)
    t.add_row("balance", f"{user.balance_fc} Gold (g)")
    t.add_row("identity file", "~/.coinfox/identity")
    console.print(Panel(t, title="arena identity", border_style="cyan"))
    return 0


def _render_arena_balance(args, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    user = arena.ensure_user(handle)
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("user", user.handle)
    t.add_row("balance", f"{user.balance_fc} Gold (g)")
    t.add_row("starting grant", "500 Gold once")
    t.add_row("loans", "up to 1000 Gold at 20% interest when balance = 0")
    t.add_row("NYFE sizing", "no leverage, no platform cap, max loss is your stake")
    console.print(Panel(t, title="Gold balance", border_style="green"))
    return 0


def _render_arena_profile(args, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    if (getattr(args, "display_name", None) is not None
            or getattr(args, "bio", None) is not None):
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
    from ..community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    post = arena.create_post(handle, args.body)
    console.print(
        f"[bold green]posted:[/] social update #{post.id} by [cyan]{post.author_handle}[/]"
    )
    return _render_arena_posts(getattr(args, "user", None), 5, console)


def _render_arena_posts(user: str | None, n: int, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    posts = arena.list_posts(handle=user, limit=max(1, int(n)))
    if not posts:
        console.print(
            "[dim]No social posts yet. "
            "Publish one with [cyan]coinfox arena say --body \"...\"[/].[/]"
        )
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
    from ..community.arena import Arena

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


def _render_arena_market(console: Console) -> int:
    from ..community.arena import Arena
    from ..community.market_hours import format_market_timestamp, market_now_text

    arena = Arena()
    session = arena.market_session()
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("exchange", "New York Fox Exchange")
    t.add_row("now", market_now_text())
    t.add_row("hours", "Mon-Fri 9:30 AM to 4:00 PM America/New_York")
    t.add_row(
        "status",
        Text("OPEN" if session.is_open else "closed",
             style="green" if session.is_open else "red"),
    )
    if session.is_open:
        t.add_row("closes", format_market_timestamp(session.closes_at_ts))
    else:
        t.add_row("next open", format_market_timestamp(session.opens_at_ts))
    t.add_row("structure", "spot-style only; no leverage")
    t.add_row("sizing", "no platform limit; if you nuke your stack, that is on you")
    t.add_row("exit rule", "you can sell anytime while NYFE is open")
    console.print(Panel(t, title="NY Fox Exchange", border_style="bright_blue"))
    console.print(
        "[dim]Shorts are simulated with cash collateral only. "
        "Max loss is your stake. This is for fun, but users should still "
        "understand sizing matters.[/]"
    )
    return 0


def _render_arena_leaderboard(n: int, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    users = arena.leaderboard(limit=max(1, int(n)))
    if not users:
        console.print(
            "[dim]No arena users yet. "
            "Set one with [cyan]coinfox arena whoami --user yourname[/].[/]"
        )
        return 0
    t = Table(title="CoinFox leaderboard", expand=True)
    t.add_column("rank", justify="right")
    t.add_column("user", style="cyan")
    t.add_column("balance", justify="right")
    t.add_column("joined", style="dim")
    for index, user in enumerate(users, start=1):
        t.add_row(str(index), user.handle, f"{user.balance_fc} FC",
                  _age_text(user.created_ts))
    console.print(t)
    return 0


def _render_arena_ideas(show_all: bool, n: int, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    ideas = arena.list_ideas(status=None if show_all else "open", limit=max(1, int(n)))
    if not ideas:
        console.print(
            "[dim]No arena ideas yet. "
            "Post one with [cyan]coinfox arena post[/].[/]"
        )
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
    from ..community.arena import Arena

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
        header.add_row(
            "closes",
            (_age_text(idea.closes_ts)
             if idea.closes_ts <= int(time.time())
             else f"in {max(0, int(idea.closes_ts - time.time())) // 3600}h"),
        )
    if idea.outcome:
        header.add_row("outcome",
                       Text(idea.outcome.upper(), style=_bias_color(idea.outcome)))

    console.print(Panel(header, title="arena idea",
                        border_style=_bias_color(idea.bias)))
    console.print(Panel(Text(idea.body), title="thesis", border_style="dim"))
    console.print(Panel(Text(idea.resolution_rule, style="dim"),
                        title="resolution rule", border_style="dim"))

    bets = arena.bets_for_idea(idea.id)
    pools: dict[str, int] = {"long": 0, "short": 0, "neutral": 0}
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
            comment_table.add_row(_age_text(comment.created_ts),
                                  comment.author_handle, comment.body)
        console.print(comment_table)
    else:
        console.print(
            "[dim]No comments yet. "
            "Add one with [cyan]coinfox arena comment[/].[/]"
        )
    return 0


def _render_arena_post(args, console: Console) -> int:
    from ..community.arena import Arena

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
    console.print(
        f"[bold green]posted:[/] idea #{idea.id} by [cyan]{idea.author_handle}[/]"
    )
    return _render_arena_show(idea.id, console)


def _render_arena_comment(args, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    comment = arena.add_comment(args.idea_id, handle, args.body)
    console.print(
        f"[bold green]comment added:[/] #{comment.id} on idea {comment.idea_id}"
    )
    return _render_arena_show(args.idea_id, console)


def _render_arena_bet(args, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    bet = arena.place_bet(args.idea_id, handle, args.direction, args.amount)
    balance = arena.balance(handle)
    console.print(
        f"[bold green]bet placed:[/] {bet.amount_fc} FC on "
        f"[bold]{bet.direction.upper()}[/] for idea {bet.idea_id}. "
        f"Balance: [cyan]{balance} FC[/]."
    )
    return _render_arena_show(args.idea_id, console)


def _render_arena_trade(args, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    position = arena.open_position(handle, args.symbol, args.direction, args.amount)
    balance = arena.balance(handle)
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("position", f"#{position.id}")
    t.add_row("symbol", position.symbol)
    t.add_row("direction",
              Text(position.direction.upper(), style=_bias_color(position.direction)))
    t.add_row("stake", f"{position.amount_fc} FC")
    t.add_row("entry", f"{position.entry_price:.2f}")
    t.add_row("balance left", f"{balance} FC")
    console.print(Panel(t, title="NYFE position opened",
                        border_style=_bias_color(position.direction)))
    console.print(
        "[dim]No leverage. No platform bet cap. "
        "If you over-size, the fox will not save you.[/]"
    )
    return 0


def _render_arena_positions(args, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    status = None if getattr(args, "all", False) else "open"
    marks = arena.marked_positions(
        handle=handle, status=status,
        limit=max(1, int(getattr(args, "n", 20))),
    )
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
        pnl = (position.realized_pnl_fc
               if position.status == "closed"
               else mark.unrealized_pnl_fc)
        pnl_text = ("n/a" if pnl is None
                    else (f"+{pnl}" if pnl > 0 else str(pnl)))
        pnl_style = ("green" if pnl and pnl > 0
                     else "red" if pnl and pnl < 0
                     else "dim")
        marked_price = ("n/a" if mark.current_price is None
                        else f"{mark.current_price:.2f}")
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
    from ..community.arena import Arena

    arena = Arena()
    if getattr(args, "leaderboard", False):
        rows = arena.stats_leaderboard(limit=max(1, int(getattr(args, "n", 10))))
        if not rows:
            console.print(
                "[dim]No arena users yet. "
                "Set one with [cyan]coinfox arena whoami --user yourname[/].[/]"
            )
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
            realized = (f"+{stat.realized_pnl_fc}" if stat.realized_pnl_fc > 0
                        else str(stat.realized_pnl_fc))
            unrealized = (f"+{stat.unrealized_pnl_fc}" if stat.unrealized_pnl_fc > 0
                          else str(stat.unrealized_pnl_fc))
            t.add_row(
                str(index), stat.handle, realized, unrealized,
                str(stat.winning_positions), str(stat.losing_positions),
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
    from ..community.arena import Arena

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
    t.add_row("exit",
              f"{position.exit_price:.2f}" if position.exit_price is not None else "n/a")
    t.add_row("pnl", Text(pnl_text + " FC", style=pnl_style))
    t.add_row("balance", f"{balance} FC")
    console.print(Panel(t, title="NYFE position closed", border_style=pnl_style))
    return 0


def _render_arena_resolve(args, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    idea = arena.resolve_idea(args.idea_id, args.outcome, handle)
    console.print(
        f"[bold green]resolved:[/] idea {idea.id} -> "
        f"[bold]{idea.outcome.upper() if idea.outcome else 'UNKNOWN'}[/]"
    )
    return _render_arena_show(args.idea_id, console)


def _render_arena_ledger(args, console: Console) -> int:
    from ..community.arena import Arena

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
        t.add_row(_age_text(int(row["created_ts"])),
                  Text(delta_text, style=style), str(row["reason"]), ref)
    console.print(t)
    return 0


def _render_arena_borrow(args, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    amount = getattr(args, "amount", 1000)
    loan = arena.borrow_gold(handle, amount)
    total_owed = loan.principal_fc + loan.interest_fc
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("handle", handle)
    t.add_row("borrowed", f"{loan.principal_fc} Gold (g)")
    t.add_row("interest (20%)", f"{loan.interest_fc} g")
    t.add_row("total owed", f"{total_owed} g")
    t.add_row("repay with", "coinfox arena repay")
    console.print(Panel(t, title="[bold yellow]Gold loan \u2014 NY Fox Exchange[/]",
                        border_style="yellow"))
    console.print("[yellow]Remember: this is make-believe Gold. Repay when you can![/]")
    return 0


def _render_arena_repay(args, console: Console) -> int:
    from ..community.arena import Arena

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    loan = arena.repay_gold(handle)
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("handle", handle)
    t.add_row("repaid", f"{loan.principal_fc + loan.interest_fc} Gold (g)")
    t.add_row("loan status", "repaid")
    console.print(Panel(t, title="[bold green]Loan repaid[/]", border_style="green"))
    return _render_arena_balance(args, console)


def _render_arena_rescue(args, console: Console) -> int:
    """Legacy rescue shim \u2014 maps to borrow_gold for backward compat."""
    from ..community.arena import Arena, BANKRUPTCY_RESCUE_FC

    arena = Arena()
    handle = _resolve_arena_user(arena, getattr(args, "user", None))
    loan = arena.borrow_gold(handle, BANKRUPTCY_RESCUE_FC)
    console.print(
        f"[bold green]Gold loan granted:[/] [cyan]{handle}[/] borrowed {loan.principal_fc} g "
        f"(owes {loan.principal_fc + loan.interest_fc} g total). "
        f"Repay with [cyan]coinfox arena repay[/]."
    )
    return _render_arena_balance(args, console)
