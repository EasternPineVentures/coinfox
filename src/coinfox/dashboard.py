"""Rich-powered dashboards. The fox watches."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .attribution import byline
from .data import FearGreed
from .intel import Intel
from .model import Verdict
from .trade import TradeIdea

FOX_WATCHING = r"""
        /\___/\
       (  o o  )    < watching BTC...
       (  =^=  )
        (______)
"""

FOX_BULL = r"""
        /\___/\
       (  ^ ^  )    < smells a pump
       (  =w=  )
        (__||__)
"""

FOX_BEAR = r"""
        /\___/\
       (  x x  )    < smells blood
       (  =v=  )
        (______)
"""

FOX_NEUTRAL = r"""
        /\___/\
       (  - -  )    < chop. patience.
       (  =_=  )
        (______)
"""


def _fox(bias: str) -> str:
    return {"long": FOX_BULL, "short": FOX_BEAR, "neutral": FOX_NEUTRAL}.get(bias, FOX_WATCHING)


def _bias_color(bias: str) -> str:
    return {"long": "bold green", "short": "bold red", "neutral": "bold yellow"}.get(bias, "white")


def _prob_bar(prob: float, width: int = 30) -> Text:
    filled = int(round(prob * width))
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if prob >= 0.58 else "red" if prob <= 0.42 else "yellow"
    return Text(bar, style=color)


def _fmt_age(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    now = datetime.now(timezone.utc)
    delta = now - dt
    s = int(delta.total_seconds())
    if s < 60:
        return f"{s}s ago"
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


def render_verdict(
    verdict: Verdict,
    symbol: str,
    timeframe: str,
    price: float,
    stats_24h: Optional[dict],
    fng: Optional[FearGreed],
) -> Panel:
    bias = verdict.bias
    pct_up = verdict.probability_up * 100.0
    conf = verdict.confidence * 100.0

    header = Table.grid(expand=True)
    header.add_column(justify="left")
    header.add_column(justify="right")
    chg_pct = float(stats_24h["priceChangePercent"]) if stats_24h else 0.0
    chg_style = "green" if chg_pct >= 0 else "red"
    header.add_row(
        Text.assemble(
            ("coinfox ", "bold magenta"),
            (f"· {symbol} ", "bold white"),
            (f"@ ${price:,.2f} ", "bold cyan"),
            (f"({chg_pct:+.2f}% 24h)", chg_style),
        ),
        Text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), style="dim"),
    )

    fox_text = Text(_fox(bias), style=_bias_color(bias))

    verdict_table = Table.grid(padding=(0, 2))
    verdict_table.add_column(justify="right", style="dim")
    verdict_table.add_column()
    verdict_table.add_row("bias", Text(bias.upper(), style=_bias_color(bias)))
    verdict_table.add_row("horizon", Text(f"next {verdict.horizon_candles} × {timeframe}"))
    verdict_table.add_row("P(up)", Text.assemble(_prob_bar(verdict.probability_up), Text(f"  {pct_up:5.1f}%")))
    verdict_table.add_row("P(down)", Text(f"{100-pct_up:5.1f}%", style="dim"))
    verdict_table.add_row("confidence", Text.assemble(_prob_bar(verdict.confidence), Text(f"  {conf:5.1f}%")))

    top = Table.grid(expand=True)
    top.add_column(ratio=1)
    top.add_column(ratio=2)
    top.add_row(Align.center(fox_text), Align.left(verdict_table))

    sigs = Table(title="signals", title_style="bold", expand=True)
    sigs.add_column("name", style="cyan")
    sigs.add_column("vote", justify="right")
    sigs.add_column("weight", justify="right", style="dim")
    sigs.add_column("contribution", justify="right")
    sigs.add_column("detail", style="dim")
    for s in verdict.signals:
        vote_style = "green" if s.vote > 0.05 else "red" if s.vote < -0.05 else "yellow"
        contrib = s.vote * s.weight
        sigs.add_row(s.name, Text(f"{s.vote:+.2f}", style=vote_style),
                     f"{s.weight:.2f}", Text(f"{contrib:+.2f}", style=vote_style), s.detail)

    extras = Table.grid(padding=(0, 2))
    extras.add_column(style="dim"); extras.add_column()
    extras.add_column(style="dim"); extras.add_column()
    e = verdict.extras
    extras.add_row("EMA20", f"${e['ema20']:,.2f}",
                   "RSI14", f"{e['rsi14']:.1f}" if e['rsi14'] == e['rsi14'] else "n/a")
    extras.add_row("EMA50", f"${e['ema50']:,.2f}", "MACD hist", f"{e['macd_hist']:+.2f}")
    extras.add_row("EMA200", f"${e['ema200']:,.2f}",
                   "BB %B", f"{e['pct_b']:.2f}" if e['pct_b'] == e['pct_b'] else "n/a")
    fng_str = f"{fng.value} ({fng.classification})" if fng else "unavailable"
    extras.add_row("F&G", fng_str, "vol z",
                   f"{e['vol_z']:+.2f}" if e['vol_z'] == e['vol_z'] else "n/a")

    body = Group(header, Text(""), top, Text(""), sigs, Text(""),
                 Panel(extras, title="context", border_style="dim"),
                 Text("experimental · not financial advice", style="dim italic"))
    return Panel(body, border_style=_bias_color(bias), title="🦊 coinfox", title_align="left")


def render_call(idea: TradeIdea) -> Panel:
    """Render an actionable trade idea — entry, stop, target, size."""
    color = {"LONG": "bold green", "SHORT": "bold red",
             "STAND ASIDE": "bold yellow"}.get(idea.action, "white")
    conv_color = {"high": "green", "medium": "yellow", "low": "red"}.get(idea.conviction, "white")

    head = Table.grid(expand=True)
    head.add_column(justify="left"); head.add_column(justify="right")
    head.add_row(
        Text.assemble((f"{idea.action}  ", color),
                      (f"· conviction: ", "dim"),
                      (idea.conviction.upper(), conv_color)),
        Text(f"horizon: next {idea.horizon_candles} × {idea.timeframe}", style="dim"),
    )

    levels = Table.grid(padding=(0, 2))
    levels.add_column(style="dim"); levels.add_column(); levels.add_column(style="dim"); levels.add_column()
    levels.add_row("entry", f"${idea.entry:,.2f}",
                   "R:R", f"{idea.rr:.2f}")
    if idea.action == "STAND ASIDE":
        levels.add_row("stop", "—", "target", "—")
        levels.add_row("risk %", "—", "reward %", "—")
    else:
        levels.add_row("stop", f"${idea.stop:,.2f}",
                       "target", f"${idea.target:,.2f}")
        levels.add_row("risk %", f"{idea.risk_pct:.2f}%",
                       "reward %", f"{idea.reward_pct:.2f}%")

    sizing = Table.grid(padding=(0, 2))
    sizing.add_column(style="dim"); sizing.add_column()
    sizing.add_row("suggested risk", Text(f"{idea.suggested_size_pct:.2f}% of bankroll",
                                          style=color if idea.suggested_size_pct > 0 else "dim"))
    sizing.add_row("raw Kelly",       f"{idea.kelly_fraction*100:.2f}%  (we use quarter-Kelly, capped at 2%)")

    body = Group(
        head,
        Text(""),
        levels,
        Text(""),
        sizing,
        Text(""),
        Panel(Text(idea.rationale), title="why", border_style="dim"),
        Text("educational tool · sized to lose well · never financial advice",
             style="dim italic"),
    )
    return Panel(body, title="🦊 the call", title_align="left", border_style=color)


def _section(panel_or_table, module_name: str):
    """Attach a byline footer to a section."""
    line = byline(module_name)
    if not line:
        return panel_or_table
    return Group(panel_or_table, Text(f"  source: {line}", style="dim italic"))


def _render_foxclaw_thought() -> Optional[object]:
    """Return a Rich Panel for the latest FoxClaw thought, or None if unavailable."""
    try:
        import time as _time
        import sqlite3
        from pathlib import Path
        db = Path.home() / ".coinfox" / "churn.sqlite"
        if not db.exists():
            return None
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT ts, bias, conviction, headline, body, provider, model "
                "FROM thoughts ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        ts, bias, conviction, headline, body, provider, model_name = row
        age_s = int(_time.time()) - int(ts)
        if age_s < 60:
            age_str = f"{age_s}s ago"
        elif age_s < 3600:
            age_str = f"{age_s // 60}m ago"
        else:
            age_str = f"{age_s // 3600}h ago"
        color = _bias_color(bias)
        g = Table.grid(padding=(0, 2))
        g.add_column(style="dim"); g.add_column()
        g.add_row("bias", Text(bias.upper(), style=color))
        g.add_row("conviction", f"{conviction}/5")
        g.add_row("headline", Text(headline, style="bold"))
        g.add_row("provider", f"{provider} ({model_name})")
        g.add_row("age", age_str)
        freshness = "[green]fresh[/]" if age_s < 1800 else "[yellow]stale (>30m)[/]"
        return Panel(
            Group(g, Text(""), Text(body, style="dim"),
                  Text(f"\n{freshness} · not advice · experimental", style="dim italic")),
            title="🦊 FoxClaw — autonomous AI read",
            border_style=color,
        )
    except Exception:
        return None



def render_intel(intel: Intel) -> Panel:
    """Render the full firehose of BTC info from all sources."""
    sections = []

    # --- FoxClaw autonomous AI read (shown first if available)
    fc_panel = _render_foxclaw_thought()
    if fc_panel is not None:
        sections.append(fc_panel)

    # --- Prices across exchanges
    if intel.prices and intel.prices.quotes:
        t = Table(title="spot prices", expand=True)
        t.add_column("exchange", style="cyan"); t.add_column("pair", style="dim")
        t.add_column("price", justify="right")
        for q in intel.prices.quotes:
            t.add_row(q.exchange, q.pair, f"${q.price:,.2f}")
        if intel.prices.median_usd is not None:
            t.add_row("[bold]median[/]", "",
                      Text(f"${intel.prices.median_usd:,.2f}", style="bold"))
        if intel.prices.spread_pct is not None:
            t.add_row("[dim]spread[/]", "",
                      Text(f"{intel.prices.spread_pct:.3f}%", style="dim"))
        sections.append(t)

    # --- Global market
    if intel.global_market:
        g = intel.global_market
        gm = Table.grid(padding=(0, 2))
        gm.add_column(style="dim"); gm.add_column()
        gm.add_row("total mcap", f"${g['total_market_cap_usd']/1e12:,.2f}T")
        gm.add_row("24h volume", f"${g['total_volume_usd']/1e9:,.1f}B")
        gm.add_row("BTC dominance", f"{g['btc_dominance_pct']:.2f}%")
        gm.add_row("ETH dominance", f"{g['eth_dominance_pct']:.2f}%")
        gm.add_row("active coins", f"{g['active_cryptocurrencies']:,}")
        sections.append(Panel(gm, title="global market (CoinGecko)", border_style="dim"))

    # --- Derivatives
    if intel.derivatives and (intel.derivatives.funding or intel.derivatives.open_interest):
        d = intel.derivatives
        tbl = Table(title="derivatives", expand=True)
        tbl.add_column("venue", style="cyan"); tbl.add_column("symbol", style="dim")
        tbl.add_column("funding", justify="right"); tbl.add_column("annualized", justify="right")
        tbl.add_column("OI notional", justify="right")
        oi_by_venue = {x.venue: x for x in d.open_interest}
        for f in d.funding:
            oi = oi_by_venue.get(f.venue)
            oi_s = f"${oi.notional_usd/1e9:,.2f}B" if (oi and oi.notional_usd) else "—"
            color = "red" if f.rate > 0.0002 else "green" if f.rate < -0.0001 else "yellow"
            tbl.add_row(f.venue, f.symbol,
                        Text(f"{f.rate*100:+.4f}%", style=color),
                        f"{f.annualized_pct:+.1f}%",
                        oi_s)
        if d.avg_funding is not None:
            tbl.add_row("[bold]avg[/]", "",
                        Text(f"{d.avg_funding*100:+.4f}%", style="bold"),
                        f"{d.avg_funding_annualized_pct:+.1f}%", "")
        if d.basis_pct is not None:
            tbl.add_row("[dim]deribit basis[/]", "",
                        Text(f"{d.basis_pct:+.3f}%", style="dim"), "", "")
        sections.append(tbl)

    # --- On-chain
    if intel.onchain:
        o = intel.onchain
        oc = Table.grid(padding=(0, 2))
        oc.add_column(style="dim"); oc.add_column()
        oc.add_column(style="dim"); oc.add_column()
        oc.add_row("block tip", f"{o.tip_height:,}" if o.tip_height else "—",
                   "blocks to halving", f"{o.blocks_to_halving:,}" if o.blocks_to_halving else "—")
        oc.add_row("hashrate", f"{o.hashrate_ehs:.1f} EH/s" if o.hashrate_ehs else "—",
                   "difficulty", f"{o.difficulty:.2e}" if o.difficulty else "—")
        oc.add_row("fee (fast)", f"{o.fee_fast_sat_vb} sat/vB" if o.fee_fast_sat_vb else "—",
                   "fee (1h)", f"{o.fee_hour_sat_vb} sat/vB" if o.fee_hour_sat_vb else "—")
        oc.add_row("mempool tx", f"{o.mempool_count:,}" if o.mempool_count else "—",
                   "mempool fees", f"{o.mempool_total_fee_btc:.2f} BTC" if o.mempool_total_fee_btc else "—")
        sections.append(Panel(oc, title="on-chain (mempool.space + blockchain.info)", border_style="dim"))

    # --- Sentiment
    if intel.sentiment:
        s = intel.sentiment
        st = Table.grid(padding=(0, 2))
        st.add_column(style="dim"); st.add_column()
        if s.fng_now:
            st.add_row("F&G now", f"{s.fng_now.value} ({s.fng_now.classification})")
        if s.fng_yesterday:
            delta = s.fng_now.value - s.fng_yesterday.value if s.fng_now else 0
            st.add_row("F&G yesterday", f"{s.fng_yesterday.value} ({delta:+d})")
        if s.fng_week_ago:
            st.add_row("F&G 7d ago", str(s.fng_week_ago.value))
        if s.coingecko_up_votes_pct is not None:
            st.add_row("CG upvotes", f"{s.coingecko_up_votes_pct:.1f}%")
        if s.coingecko_community_score is not None:
            st.add_row("CG community", f"{s.coingecko_community_score:.1f}")
        if s.coingecko_developer_score is not None:
            st.add_row("CG developer", f"{s.coingecko_developer_score:.1f}")
        sections.append(Panel(st, title="sentiment", border_style="dim"))

    # --- Macro
    if intel.macro and intel.macro.series:
        mt = Table(title="macro (Stooq)", expand=True)
        mt.add_column("series", style="cyan"); mt.add_column("last", justify="right")
        mt.add_column("Δ %", justify="right")
        for name, val in intel.macro.series.items():
            chg = intel.macro.changes_pct.get(name)
            chg_text = Text(f"{chg:+.2f}%", style="green" if (chg or 0) >= 0 else "red") \
                if chg is not None else Text("—", style="dim")
            mt.add_row(name, f"{val:,.2f}", chg_text)
        sections.append(mt)

    # --- News
    if intel.news and intel.news.headlines:
        nt = Table(title="latest BTC news", expand=True)
        nt.add_column("source", style="cyan", no_wrap=True)
        nt.add_column("when", style="dim", no_wrap=True)
        nt.add_column("headline")
        for h in intel.news.headlines[:12]:
            nt.add_row(h.source, _fmt_age(h.published), h.title)
        sections.append(nt)

    # --- Social
    if intel.social and intel.social.top_posts:
        rt = Table(title="r/Bitcoin hot", expand=True)
        rt.add_column("score", justify="right", style="yellow")
        rt.add_column("comments", justify="right", style="dim")
        rt.add_column("title")
        for p in intel.social.top_posts[:8]:
            rt.add_row(str(p.score), str(p.num_comments), p.title)
        sections.append(rt)

    # --- Dev
    if intel.dev and (intel.dev.latest_release or intel.dev.recent_commits):
        dv = []
        if intel.dev.latest_release:
            r = intel.dev.latest_release
            dv.append(Text.assemble(("latest release: ", "dim"),
                                    (f"{r.tag} ", "bold"),
                                    (f"({r.published_at})", "dim")))
        if intel.dev.recent_commits:
            ct = Table(title="bitcoin/bitcoin recent commits", expand=True)
            ct.add_column("sha", style="dim"); ct.add_column("author", style="cyan")
            ct.add_column("message")
            for c in intel.dev.recent_commits:
                ct.add_row(c.sha, c.author, c.message)
            dv.append(ct)
        sections.append(Panel(Group(*dv), title="development", border_style="dim"))

    # --- Errors
    if intel.errors:
        et = Table(title="source errors", expand=True, border_style="red")
        et.add_column("source", style="red"); et.add_column("error", style="dim")
        for k, v in intel.errors.items():
            et.add_row(k, v)
        sections.append(et)

    if not sections:
        sections.append(Text("No intel could be gathered. Check network connectivity.", style="red"))

    # Credits footer — who built the sources powering this view
    from .credits import collect as _collect_credits
    book = _collect_credits()
    source_credits = sorted({
        f"@{c.github}" if c.github else c.name
        for c in book.all if c.role == "source"
    })
    if source_credits:
        sections.append(Text(
            "intel powered by: " + " · ".join(source_credits) +
            "    (run `coinfox credits` to see the full Hall of Foxes)",
            style="dim italic",
        ))

    spaced = []
    for s in sections:
        spaced.append(s)
        spaced.append(Text(""))
    body = Group(*spaced)
    return Panel(body, title="🦊 coinfox intel — free BTC info, from everywhere",
                 title_align="left", border_style="magenta")
