"""Seed CoinFox with a believable demo community.

Wipes the social store and fills it with users, discussions, trade calls, votes
and threaded comments so the feed feels alive (not empty / not obviously seeded).

Run:  PYTHONPATH=src python scripts/seed_demo.py
The default DB (~/.coinfox/social.sqlite) is the one the running API serves.
"""
from __future__ import annotations

import random
from contextlib import closing

from coinfox.community.social import SocialStore
from coinfox.data import DataError, fetch_spot

random.seed(7)


def _spot(symbol: str, fallback: float) -> float:
    """Live price so seeded crypto calls look real and sit near market."""
    try:
        return round(fetch_spot(symbol), 2)
    except DataError:
        return fallback


def wipe(store: SocialStore) -> None:
    """Clear demo *content* but NEVER delete users — wiping users nukes real
    accounts people have claimed. Posts/votes/comments are safe to reset."""
    with closing(store._connect()) as conn, conn:  # noqa: SLF001 - intentional for seeding
        for table in ("comment_votes", "votes", "predictions", "comments", "posts"):
            conn.execute(f"DELETE FROM {table}")


def get_or_create(store: SocialStore, name: str) -> str:
    """Idempotent demo user — survives re-runs without colliding on the handle."""
    from coinfox.community.social import SocialError
    try:
        return store.create_user(name)["id"]
    except SocialError:
        from contextlib import closing as _closing
        with _closing(store._connect()) as conn:
            row = conn.execute("SELECT id FROM users WHERE username = ?", (name,)).fetchone()
        return row["id"]


def main() -> None:
    store = SocialStore()
    wipe(store)

    # --- a cast of regulars, each with a distinct voice ---------------------
    people = {
        name: get_or_create(store, name)
        for name in [
            "macro_mike", "swing_sara", "btc_basil", "fed_watch_fran", "quant_quinn",
            "wolf_fan_will", "options_olive", "newbie_nate", "chartist_chen", "vol_vera",
        ]
    }

    def cred(uid: str, wins: int, losses: int) -> None:
        """Give a user a real track record by resolving past calls."""
        for _ in range(wins):
            pid = store.create_post(uid, _call("SPY", "long", 500, 495, 510))["id"]
            store.resolve_post(pid, "tp_hit")
        for _ in range(losses):
            pid = store.create_post(uid, _call("SPY", "long", 500, 495, 510))["id"]
            store.resolve_post(pid, "sl_hit")

    cred(people["quant_quinn"], 14, 4)     # sharp
    cred(people["swing_sara"], 9, 6)       # solid
    cred(people["btc_basil"], 7, 7)        # coin-flip
    cred(people["newbie_nate"], 1, 5)      # learning

    # --- live, actionable trade calls (crypto levels anchored to live price) -
    btc = _spot("BTCUSDT", 67420)
    eth = _spot("ETHUSDT", 3140)
    calls = [
        (people["btc_basil"], _call("BTCUSDT", "long", btc, round(btc * 0.97, 2), round(btc * 1.05, 2),
            "Holding the breakout retest with strong spot bid. Targeting prior high.")),
        (people["swing_sara"], _call("NVDA", "long", 122.4, 118.0, 134.0,
            "Bull flag on the daily into earnings. Risk defined under the 50DMA.")),
        (people["vol_vera"], _call("ETHUSDT", "short", eth, round(eth * 1.04, 2), round(eth * 0.92, 2),
            "Rejected the descending trendline, funding still hot. Fade the pop.")),
        (people["chartist_chen"], _call("SPY", "long", 548, 544, 556,
            "VWAP reclaim into a trend day, breadth green across sectors.")),
    ]
    call_ids = [store.create_post(uid, draft)["id"] for uid, draft in calls]

    # --- free-form discussions (the social heart) --------------------------
    discussions = [
        (people["macro_mike"], "Are we pricing in too many rate cuts for 2026?",
         "Curve says 3 cuts but the data is hot. Feels like the market is front-running the Fed again. What are you all seeing?", "MACRO"),
        (people["wolf_fan_will"], "Just rewatched Wolf of Wall Street — what got you into trading?",
         "Half meme, half serious. Drop your origin story below.", "GENERAL"),
        (people["fed_watch_fran"], "CPI tomorrow — how are you positioning into the print?",
         "Flat and waiting, or taking a side? I hate holding through data but the setup is tempting.", "MACRO"),
        (people["options_olive"], "IV is dirt cheap right now. Anyone selling premium?",
         "30-day IV rank near lows. Feels like free money until it isn't. Talk me out of it.", "OPTIONS"),
    ]
    disc_ids = [store.create_discussion(uid, {"title": t, "body": b, "topic": tag})["id"]
                for uid, t, b, tag in discussions]

    everyone = list(people.values())

    def spread_votes(post_id: str, boosts: int, fades: int) -> None:
        voters = random.sample(everyone, min(boosts + fades, len(everyone)))
        for v in voters[:boosts]:
            store.vote(v, post_id, "boost")
        for v in voters[boosts:boosts + fades]:
            store.vote(v, post_id, "fade")

    # Popular stuff floats up; one contrarian call gets faded into the negative.
    spread_votes(disc_ids[0], 6, 0)
    spread_votes(disc_ids[1], 3, 0)
    spread_votes(disc_ids[2], 4, 1)
    spread_votes(disc_ids[3], 2, 0)
    spread_votes(call_ids[0], 5, 0)
    spread_votes(call_ids[1], 4, 1)
    spread_votes(call_ids[2], 1, 4)   # the crowd fades this one
    spread_votes(call_ids[3], 2, 0)

    # --- threaded conversation ---------------------------------------------
    threads = {
        disc_ids[0]: [
            (people["quant_quinn"], "Front-running for sure. Two cuts max unless jobs roll over."),
            (people["swing_sara"], "Bonds disagree with you but I lean your way."),
            (people["newbie_nate"], "Why does the Fed care about jobs more than CPI right now?"),
            (people["macro_mike"], "@newbie_nate dual mandate — employment + prices. Right now jobs is the swing factor."),
        ],
        disc_ids[1]: [
            (people["btc_basil"], "Saw a guy 100x a meme coin on stream. Never recovered lol."),
            (people["options_olive"], "Honestly? Boredom during 2020. Stayed for the math."),
        ],
        call_ids[0]: [
            (people["vol_vera"], "Watch the funding here, longs are crowded."),
            (people["btc_basil"], "Fair, tight stop under 65.9 keeps it clean."),
        ],
        call_ids[2]: [
            (people["chartist_chen"], "Shorting into support? Bold."),
            (people["vol_vera"], "Support's already cracked on the 4h imo."),
        ],
    }
    for post_id, msgs in threads.items():
        made = [store.add_comment(uid, post_id, content) for uid, content in msgs]
        # Let the community lift the best replies so a clear top take emerges.
        if made:
            top = made[0]
            for v in random.sample(everyone, 3):
                store.vote_comment(v, top["id"], "boost")
            if len(made) > 2:
                store.vote_comment(everyone[0], made[-1]["id"], "fade")

    feed = store.list_feed_ranked(limit=50)
    print(f"Seeded {len(everyone)} users, {len(call_ids)} live calls, "
          f"{len(disc_ids)} discussions. Feed shows {len(feed)} posts.")


def _call(symbol, direction, entry, stop, target, reasoning=None):
    return {
        "symbol": symbol, "direction": direction, "entry_price": entry,
        "stop_loss": stop, "take_profit": target, "reasoning": reasoning,
    }


if __name__ == "__main__":
    main()
