"""Render the credits — who built what.

The fox watches BTC. The community watches the fox. Everyone gets credit.
"""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .attribution import CreditBook, collect


def render_credits(book: CreditBook | None = None) -> Panel:
    book = book or collect()

    header = Text.assemble(
        ("🦊 Hall of Foxes", "bold magenta"),
        ("\n", ""),
        (f"{len(book.all)} contributions from {book.contributor_count} contributor(s). ", "dim"),
        ("Add yours: ", "dim"),
        ("python -m coinfox new-source <name> --author <handle>", "bold cyan"),
    )

    table = Table(expand=True)
    table.add_column("contributor", style="bold cyan", no_wrap=True)
    table.add_column("role", style="yellow", no_wrap=True)
    table.add_column("module", style="dim", no_wrap=True)
    table.add_column("contribution")
    table.add_column("added", style="dim", no_wrap=True)

    for c in book.all:
        who = c.name + (f"  @{c.github}" if c.github else "")
        table.add_row(who, c.role, c.module, c.contribution, c.added)

    leaderboard = Table(title="leaderboard", expand=True)
    leaderboard.add_column("contributor", style="bold cyan")
    leaderboard.add_column("contributions", justify="right", style="yellow")
    leaderboard.add_column("areas", style="dim")
    ranked = sorted(book.by_contributor.items(),
                    key=lambda kv: (-len(kv[1]), kv[0].lower()))
    for handle, items in ranked:
        first = items[0]
        display = first.name + (f"  @{first.github}" if first.github else "")
        roles = ", ".join(sorted({i.role for i in items}))
        leaderboard.add_row(display, str(len(items)), roles)

    footer = Text(
        "Want your handle here? Open a PR adding a source — there's a 5-minute scaffolder and "
        "a CONTRIBUTORS.md waiting for you.",
        style="italic dim",
    )

    return Panel(
        Group(header, Text(""), table, Text(""), leaderboard, Text(""), footer),
        title="🦊 coinfox · credits",
        title_align="left",
        border_style="magenta",
    )
