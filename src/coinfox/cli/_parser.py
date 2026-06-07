"""CLI argument parser - `_build_parser()` and subcommand helpers."""

from __future__ import annotations

import argparse

from ._shared import _watch_args


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

    tune = pulse_sub.add_parser("tune-regime",
                                help="tune regime detector thresholds on deterministic cases")
    tune.add_argument("--explain", action="store_true", help="explain this command")

    feedback = pulse_sub.add_parser("feedback-report",
                                    help="summarize anonymous feedback events")
    feedback.add_argument("--symbol", help="filter report to one symbol")
    feedback.add_argument("--db", default=None, help="path to feedback sqlite database")
    feedback.add_argument("--limit", type=int, default=1000,
                          help="max feedback events to inspect")
    feedback.add_argument("--json", action="store_true", help="print machine-readable JSON")
    feedback.add_argument("--explain", action="store_true", help="explain this command")

    run = pulse_sub.add_parser("run",
                               help="always-on pulse with live status and countdown")
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

    # `credits` - Hall of Foxes
    sub.add_parser("credits", help="show contributor credits (the Hall of Foxes)")

    # `new-source` - scaffold a new community source module
    ns = sub.add_parser("new-source",
                        help="scaffold a new source module (you in CONTRIBUTORS, auto-registered)")
    ns.add_argument("name", help="source name (e.g. 'lightning-stats')")
    ns.add_argument("--author", required=True, help="your GitHub handle (no @)")
    ns.add_argument("--name-display", default=None,
                    help="display name (default: same as --author)")
    ns.add_argument("--endpoint", default="https://api.example.com/btc")
    ns.add_argument("--why", default="TODO: what does this tell us about BTC?")
    ns.add_argument("--contribution", default=None)

    api = sub.add_parser("api", help="run the CoinFox HTTP API")
    api.add_argument("--host", default="127.0.0.1", help="host to bind (default 127.0.0.1)")
    api.add_argument("--port", type=int, default=8000, help="port to bind (default 8000)")
    api.add_argument("--reload", action="store_true",
                     help="reload when source files change")

    # `pulse` - AI context background commands.
    pulse = sub.add_parser("pulse", help="AI market pulse: status, tick, history, run")
    _add_pulse_subcommands(pulse)

    arena = sub.add_parser("arena",
                           help="CoinFox arena: ideas, discussion, bets, leaderboard")
    arena_sub = arena.add_subparsers(dest="arena_cmd")

    whoami = arena_sub.add_parser("whoami", help="show or set your local arena handle")
    whoami.add_argument("--user", help="set your local arena handle")

    balance = arena_sub.add_parser("balance", help="show your Gold balance")
    balance.add_argument("--user", help="override the local arena handle")

    profile = arena_sub.add_parser("profile", help="show or update an arena profile")
    profile.add_argument("--user", help="override the local arena handle")
    profile.add_argument("--display-name", help="set the public display name")
    profile.add_argument("--bio", help="set the public bio")

    say = arena_sub.add_parser("say",
                               help="publish a social post to your profile and the shared feed")
    say.add_argument("--user", help="override the local arena handle")
    say.add_argument("--body", required=True)

    posts = arena_sub.add_parser("posts",
                                 help="list social posts for one user or everyone")
    posts.add_argument("--user", help="filter to one arena handle")
    posts.add_argument("-n", type=int, default=20,
                       help="how many posts to show (default 20)")

    feed = arena_sub.add_parser("feed", help="show the shared arena feed")
    feed.add_argument("--user", help="filter to one arena handle")
    feed.add_argument("-n", type=int, default=20,
                      help="how many events to show (default 20)")

    leaderboard = arena_sub.add_parser("leaderboard", help="top Gold holders")
    leaderboard.add_argument("-n", type=int, default=10,
                             help="how many users to show (default 10)")

    ideas = arena_sub.add_parser("ideas", help="list arena ideas")
    ideas.add_argument("--all", action="store_true", help="include resolved ideas")
    ideas.add_argument("-n", type=int, default=20,
                       help="how many ideas to show (default 20)")

    show = arena_sub.add_parser("show", help="show one idea with comments and pools")
    show.add_argument("idea_id", type=int)

    post = arena_sub.add_parser("post", help="post a new trade idea")
    post.add_argument("--user", help="override the local arena handle")
    post.add_argument("--title", required=True)
    post.add_argument("--body", required=True)
    post.add_argument("--symbol", default="BTCUSDT")
    post.add_argument("--bias", default="long",
                      choices=["long", "short", "neutral"])
    post.add_argument("--rule", required=True, help="explicit settlement rule")
    post.add_argument("--hours", type=int, default=24,
                      help="betting window in hours before the idea closes (default 24)")

    comment = arena_sub.add_parser("comment", help="add a comment to an arena idea")
    comment.add_argument("idea_id", type=int)
    comment.add_argument("--user", help="override the local arena handle")
    comment.add_argument("--body", required=True)

    bet = arena_sub.add_parser("bet", help="stake Gold on an idea outcome")
    bet.add_argument("idea_id", type=int)
    bet.add_argument("--user", help="override the local arena handle")
    bet.add_argument("--amount", type=int, required=True)
    bet.add_argument("--direction", required=True,
                     choices=["long", "short", "neutral"])

    market = arena_sub.add_parser("market",
                                  help="show New York Fox Exchange trading hours and rules")

    trade = arena_sub.add_parser("trade",
                                 help="open a NY Fox Exchange spot-style position during market hours")
    trade.add_argument("--user", help="override the local arena handle")
    trade.add_argument("--symbol", default="BTCUSDT")
    trade.add_argument("--direction", required=True, choices=["long", "short"])
    trade.add_argument("--amount", type=int, required=True)

    positions = arena_sub.add_parser("positions",
                                     help="show your NY Fox Exchange positions")
    positions.add_argument("--user", help="override the local arena handle")
    positions.add_argument("--all", action="store_true",
                           help="include closed positions")
    positions.add_argument("-n", type=int, default=20,
                           help="how many positions to show (default 20)")

    stats = arena_sub.add_parser("stats",
                                 help="show user stats or the top arena performers")
    stats.add_argument("--user", help="override the local arena handle")
    stats.add_argument("--leaderboard", action="store_true",
                       help="show the stats leaderboard instead of one user")
    stats.add_argument("-n", type=int, default=10,
                       help="how many leaderboard rows to show (default 10)")

    exit_trade = arena_sub.add_parser("exit",
                                      help="close an open NY Fox Exchange position during market hours")
    exit_trade.add_argument("position_id", type=int)
    exit_trade.add_argument("--user", help="override the local arena handle")

    resolve = arena_sub.add_parser("resolve", help="resolve an idea and settle bets")
    resolve.add_argument("idea_id", type=int)
    resolve.add_argument("--user", help="override the local arena handle")
    resolve.add_argument("--outcome", required=True,
                         choices=["long", "short", "neutral"])

    ledger = arena_sub.add_parser("ledger", help="show recent Gold ledger events")
    ledger.add_argument("--user", help="override the local arena handle")
    ledger.add_argument("-n", type=int, default=20,
                        help="how many entries to show (default 20)")

    borrow = arena_sub.add_parser("borrow",
                                  help="borrow up to 1000 Gold when your balance hits 0")
    borrow.add_argument("--user", help="override the local arena handle")
    borrow.add_argument("--amount", type=int, default=1000,
                        help="how much Gold to borrow (default and max: 1000)")

    repay = arena_sub.add_parser("repay",
                                 help="repay your outstanding Gold loan (principal + interest)")
    repay.add_argument("--user", help="override the local arena handle")

    # legacy top-level flags (so `python -m coinfox` still works)
    _watch_args(p)
    return p
