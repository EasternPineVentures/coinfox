"""Pulse CLI render functions."""

from __future__ import annotations

import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ._shared import _bias_color
from ..utils.json_utils import safe_json_dumps


def _render_churn_status(args, console: Console) -> int:
    from ..ai.churn import ChurnDaemon
    from ..ai.router import FoxClaw
    from ..ai.regime import run_regime_benchmark

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
        avail = (Text("YES", style="green") if p["available"]
                 else Text("no", style="dim red"))
        t.add_row(p["name"], p["tier"], p["key_env"] or "\u2014", avail,
                  str(p["ok"]), str(p["fail"]), p["model"] or "\u2014")
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
        st.add_row("overall reliability",
                   f"{float(source_rel.get('overall', 0.0)) * 100:.1f}%")
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
        rt.add_row("confidence",
                   f"{float(regime.get('confidence', 0.0)) * 100:.1f}%")
        metrics = regime.get("metrics")
        if isinstance(metrics, dict):
            rt.add_row("trend strength",
                       f"{float(metrics.get('trend_strength', 0.0)):.3f}")
            rt.add_row("ewma vol", f"{float(metrics.get('ewma_vol', 0.0)):.5f}")
            rt.add_row("panic drop",
                       f"{float(metrics.get('panic_drop_pct', 0.0)):.2f}%")
            rt.add_row("vol spike",
                       f"{float(metrics.get('panic_volume_mult', 0.0)):.2f}x")
        console.print(Panel(rt, title="regime", border_style="dim"))

    if thought:
        age_s = int(time.time()) - thought.ts
        age_str = (f"{age_s // 60}m {age_s % 60}s ago"
                   if age_s < 3600
                   else f"{age_s // 3600}h ago")
        g = Table.grid(padding=(0, 2))
        g.add_column(style="dim")
        g.add_column()
        g.add_row("bias", Text(thought.bias.upper(), style=_bias_color(thought.bias)))
        g.add_row("conviction", f"{thought.conviction}/5")
        g.add_row("headline", thought.headline)
        g.add_row("provider", f"{thought.provider} ({thought.model})")
        g.add_row("age", age_str)
        console.print(Panel(g, title="last AI context read",
                            border_style=_bias_color(thought.bias)))
        console.print(Panel(Text(thought.body, style="dim"),
                            title="reasoning", border_style="dim"))
    else:
        console.print(
            "[dim]No AI context reads stored yet. "
            "Run [cyan]coinfox pulse tick[/] to generate one.[/]"
        )
    return 0


def _render_churn_tick(console: Console) -> int:
    from ..ai.churn import ChurnDaemon

    daemon = ChurnDaemon()
    console.print("[dim]Gathering intel and asking the AI context layer...[/]")
    start = time.time()
    thought = daemon.tick_once()
    elapsed = time.time() - start
    if not thought:
        console.print(
            "[bold red]pulse failed:[/] no AI provider answered. "
            "Install Ollama or set at least one API key env var. "
            "Run [cyan]coinfox pulse status[/] to see available providers."
        )
        return 1
    g = Table.grid(padding=(0, 2))
    g.add_column(style="dim")
    g.add_column()
    g.add_row("bias", Text(thought.bias.upper(), style=_bias_color(thought.bias)))
    g.add_row("conviction", f"{thought.conviction}/5")
    g.add_row("headline", thought.headline)
    g.add_row("provider", f"{thought.provider} ({thought.model})")
    g.add_row("elapsed", f"{elapsed:.1f}s")
    console.print(Panel(g, title="AI context read",
                        border_style=_bias_color(thought.bias)))
    console.print(Panel(Text(thought.body), title="reasoning", border_style="dim"))
    console.print("[dim]AI read stored in local pulse history[/]")
    return 0


def _render_churn_history(n: int, console: Console) -> int:
    from ..ai.churn import ChurnDaemon

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
        f"[dim]drift: [green]{long_c}L[/] / [red]{short_c}S[/] / "
        f"[yellow]{neutral_c}N[/]  flips: {flips}[/]"
    )
    return 0


def _render_churn_metrics(window: int, horizon_steps: int, neutral_band_pct: float,
                          console: Console) -> int:
    from ..ai.churn import ChurnDaemon

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
    t.add_row("weighted hit rate",
              f"{float(r.get('weighted_hit_rate', 0.0)) * 100:.1f}%")
    t.add_row("brier-like", f"{float(r.get('brier_like', 0.0)):.4f}")
    t.add_row("strange-market rate",
              f"{float(r.get('strange_rate', 0.0)) * 100:.1f}%")
    console.print(t)
    console.print(
        "[dim]Note: this is online directional scoring from stored thought history, "
        "not a guarantee.[/]"
    )
    return 0


def _render_churn_replay(args, console: Console) -> int:
    from pathlib import Path

    from ..ai.replay import run_replay_quality_gate

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

    status = (Text("PASS", style="bold green") if result.get("passed")
              else Text("FAIL", style="bold red"))
    t = Table(title="Pulse replay quality gate", expand=True)
    t.add_column("metric", style="dim")
    t.add_column("value")
    t.add_row("status", status)
    t.add_row("source", str(result.get("source", "unknown")))
    t.add_row("sample size", str(report.get("sample_size", 0)))
    t.add_row("horizon (steps)",
              str(report.get("horizon_steps", getattr(args, "horizon_steps", 6))))
    t.add_row("hit rate", f"{float(report.get('hit_rate', 0.0)) * 100:.1f}%")
    t.add_row("weighted hit rate",
              f"{float(report.get('weighted_hit_rate', 0.0)) * 100:.1f}%")
    t.add_row("brier-like", f"{float(report.get('brier_like', 0.0)):.4f}")
    t.add_row("min sample", str(thresholds.get("min_sample_size", 0)))
    t.add_row("min hit rate",
              f"{float(thresholds.get('min_hit_rate', 0.0)) * 100:.1f}%")
    t.add_row("max brier-like",
              f"{float(thresholds.get('max_brier_like', 0.0)):.4f}")
    console.print(t)

    checks = result.get("checks", {})
    ct = Table(title="Gate checks", expand=True)
    ct.add_column("check", style="dim")
    ct.add_column("result")
    for name in ("sample_size", "hit_rate", "brier_like"):
        ok = bool(checks.get(name))
        ct.add_row(name, Text("ok" if ok else "fail",
                              style="green" if ok else "red"))
    console.print(ct)
    return 0 if result.get("passed") else 1


def _render_churn_tune_regime(console: Console) -> int:
    from ..ai.regime import tune_regime_thresholds

    result = tune_regime_thresholds()
    baseline = result.get("baseline", {})
    best = result.get("best", {})
    cfg = result.get("recommended_config", {})

    t = Table(title="Regime threshold tuner", expand=True)
    t.add_column("metric", style="dim")
    t.add_column("baseline")
    t.add_column("best")
    t.add_row("accuracy",
              f"{float(baseline.get('accuracy', 0.0)) * 100:.1f}%",
              f"{float(best.get('accuracy', 0.0)) * 100:.1f}%")
    t.add_row("mean confidence",
              f"{float(baseline.get('mean_confidence', 0.0)) * 100:.1f}%",
              f"{float(best.get('mean_confidence', 0.0)) * 100:.1f}%")
    t.add_row("sample size",
              str(baseline.get("sample_size", 0)), str(best.get("sample_size", 0)))
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
        "Pulse is CoinFox\u2019s always-on market read loop. It checks sources, gathers "
        "context, stores reads, and exposes health so the system stays auditable."
    )
    safety = (
        "Safety note: CoinFox is educational market intelligence. It does not place "
        "trades or know your personal risk."
    )
    console.print(Panel(Text(f"{text}\n\n{safety}"),
                        title=f"pulse {command} --explain", border_style="cyan"))
    return 0


def _render_pulse_feedback_report(args, console: Console) -> int:
    from pathlib import Path

    from ..feedback import build_feedback_report, format_feedback_report

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
    console.print(Panel(format_feedback_report(report),
                        title="Feedback learning report", border_style="cyan"))
    return 0


def _render_bias(args, console: Console) -> int:
    from ..bias import get_bias

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

    color = {"LONG": "bold green", "SHORT": "bold red", "NEUTRAL": "bold yellow"}.get(
        read.bias, "white"
    )
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
        t.add_row("thesis check",
                  f"{read.invalidation.type} ${read.invalidation.level:,.2f}")

    drivers = Table(title="top drivers", expand=True)
    drivers.add_column("signal", style="cyan")
    drivers.add_column("lean", justify="center")
    drivers.add_column("contrib", justify="right")
    drivers.add_column("detail", style="dim")
    for driver in read.drivers:
        lean = str(driver["lean"])
        lean_color = {"LONG": "green", "SHORT": "red", "NEUTRAL": "yellow"}.get(
            lean, "white"
        )
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
    from rich.live import Live

    from ..ai.churn import ChurnDaemon

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
        learning = (latest_digest.get("learning")
                    if isinstance(latest_digest, dict) else None)
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
        runtime.add_row("heartbeat age",
                        "n/a" if hb_age is None else f"{int(hb_age)}s")

        if last_thought:
            runtime.add_row("last bias",
                            Text(last_thought.bias.upper(),
                                 style=_bias_color(last_thought.bias)))
            runtime.add_row("conviction", f"{last_thought.conviction}/5")
            runtime.add_row("provider",
                            f"{last_thought.provider} ({last_thought.model})")
            runtime.add_row("last run", f"{last_elapsed:.1f}s")
            runtime.add_row("headline", last_thought.headline)

        hint_style = "yellow" if last_error else "dim"
        hint = (last_error
                or "This panel updates every second with what the AI loop is doing.")
        body = [
            Panel(top, title="AI context", border_style="cyan"),
            Panel(runtime, title="runtime", border_style="green"),
        ]
        if isinstance(learning, dict):
            ltbl = Table.grid(padding=(0, 2))
            ltbl.add_column(style="dim")
            ltbl.add_column()
            ltbl.add_row("strange market",
                         "YES" if learning.get("strange_market") else "no")
            ltbl.add_row("anomaly score", str(learning.get("anomaly_score", 0.0)))
            ltbl.add_row("top feature",
                         str(learning.get("top_feature") or "n/a"))
            ltbl.add_row("sample size", str(learning.get("sample_size", 0)))
            body.append(Panel(ltbl, title="learning", border_style="magenta"))
        if last_thought:
            body.append(Panel(Text(last_thought.body, style="dim"),
                               title="latest reasoning", border_style="dim"))
        body.append(Text(hint, style=hint_style))
        return Panel(Group(*body), title="\U0001f98a coinfox pulse run",
                     border_style="bright_blue")

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
                    last_error = (
                        "No provider answered this cycle. "
                        "Check keys with `coinfox pulse status`."
                    )
                    phase = "sleeping (last cycle failed)"
                else:
                    last_thought = thought
                    last_error = None
                    phase = "sleeping"
                next_run_at = time.time() + interval
            live.update(_view())
            time.sleep(1)
