"""Trading-flavored anonymous username generator (Reddit-style).

Two flavors are mixed:
  * ``ADJECTIVE + CREATURE`` combos (e.g. "LeveragedLynx", "BullishBeaver") with
    an optional number suffix, like Reddit's "Adjective_Noun_42".
  * Hand-written witty market handles (e.g. "StopLossStan", "DiamondHandsDan").

Names are kept market-themed but tasteful — no profanity, no real tickers, and
nothing implying a real coin/token. Output is CamelCase with no spaces so it
drops straight into a handle field.
"""

from __future__ import annotations

import random
from typing import List, Optional

# Market/trading-flavored adjectives that read fine in front of a creature.
ADJECTIVES = [
    "Bullish", "Bearish", "Leveraged", "Liquid", "Volatile", "Hawkish",
    "Dovish", "Inverted", "Compounding", "Hedged", "Parabolic", "Contrarian",
    "Diamond", "Golden", "Diversified", "Overbought", "Oversold", "Margin",
    "Capital", "Bullmarket", "Steady", "Patient", "Sneaky", "Caffeinated",
    "Nocturnal", "Relentless", "Calculated", "Lucky",
]

# Animals (with a fox nod to the brand) plus a few trader personas.
CREATURES = [
    "Fox", "Bull", "Bear", "Wolf", "Whale", "Shark", "Hawk", "Ox", "Falcon",
    "Lynx", "Otter", "Badger", "Mongoose", "Raven", "Stag", "Beaver",
    "Trader", "Scalper", "Swinger", "Hodler", "Maverick", "Tycoon", "Baron",
    "Mogul", "Sniper", "Quant", "Chartist", "Pilot",
]

# Witty, self-contained handles in the spirit of trading-desk humor.
WITTY = [
    "StopLossStan", "DiamondHandsDan", "PaperHandsPete", "TheBagholder",
    "BuyHighSellLow", "CandlestickMaker", "ShortSqueezeSue", "MarginCallMolly",
    "TheGapFiller", "WyckoffWizard", "FibonacciFox", "DeadCatBouncer",
    "BullTrapBilly", "SidewaysSam", "RektRanger", "HodlHound", "ThetaGangGus",
    "GreenCandleGremlin", "SupportAndRhonest", "TrendIsYourFriend",
    "BreakoutBarry", "PullbackPaula", "MeanReversionMax", "VolatilityVic",
    "TheLiquidityFairy", "RiskOnRiley", "DipBuyerDee", "MoonMissionMurphy",
    "AlwaysEarlyAlice", "ProfitTakerPat",
]

# Roughly how often a generated name uses a witty handle vs an adjective combo.
_WITTY_SHARE = 0.4


def suggest(rng: Optional[random.Random] = None) -> str:
    """Return a single suggested username."""
    rng = rng or random
    if rng.random() < _WITTY_SHARE:
        name = rng.choice(WITTY)
    else:
        name = f"{rng.choice(ADJECTIVES)}{rng.choice(CREATURES)}"
    # ~half the time, add a short number suffix to keep collisions down.
    if rng.random() < 0.5:
        name = f"{name}{rng.randint(2, 99)}"
    return name


def suggest_batch(count: int = 5, rng: Optional[random.Random] = None) -> List[str]:
    """Return up to ``count`` distinct suggestions (1..20)."""
    rng = rng or random
    count = max(1, min(int(count), 20))
    seen: List[str] = []
    # Cap attempts so a small word pool can't loop forever.
    for _ in range(count * 12):
        candidate = suggest(rng)
        if candidate not in seen:
            seen.append(candidate)
        if len(seen) >= count:
            break
    return seen
