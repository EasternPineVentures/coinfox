"""Parallel aggregator over all `coinfox.sources` fetchers.

Returns an `Intel` bundle. Failures in any single source are isolated — the
rest still run. Use `gather()` for a one-shot snapshot of "everything we
know about BTC right now from the open web".
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .sources import chainlink, derivatives, dev, macro, news, onchain, prices, sentiment, social


@dataclass
class Intel:
    prices: Optional[prices.PriceSnapshot] = None
    global_market: Optional[Dict[str, Any]] = None
    chainlink: Optional[chainlink.ChainlinkSnapshot] = None
    derivatives: Optional[derivatives.DerivSnapshot] = None
    onchain: Optional[onchain.OnchainSnapshot] = None
    news: Optional[news.NewsSnapshot] = None
    social: Optional[social.SocialSnapshot] = None
    dev: Optional[dev.DevSnapshot] = None
    macro: Optional[macro.MacroSnapshot] = None
    sentiment: Optional[sentiment.SentimentSnapshot] = None
    errors: Dict[str, str] = field(default_factory=dict)


SOURCES = {

    "prices":        prices.fetch_prices,
    "global_market": prices.fetch_global_market,
    "chainlink":     chainlink.fetch_chainlink,
    "derivatives":   derivatives.fetch_derivatives,
    "onchain":       onchain.fetch_onchain,
    "news":          news.fetch_news,
    "social":        social.fetch_reddit,
    "dev":           dev.fetch_dev,
    "macro":         macro.fetch_macro,
    "sentiment":     sentiment.fetch_sentiment,
}


def gather(max_workers: int = 10, timeout: int = 25) -> Intel:
    intel = Intel()
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fn): name for name, fn in SOURCES.items()}
        for fut in as_completed(futures, timeout=timeout):
            name = futures[fut]
            try:
                setattr(intel, name, fut.result())
            except Exception as e:  # noqa: BLE001
                intel.errors[name] = f"{type(e).__name__}: {e}"
    return intel
