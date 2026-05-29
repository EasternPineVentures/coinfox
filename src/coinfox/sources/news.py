"""News headlines from public RSS feeds — no API keys needed."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional

from ._http import get_text

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "source", "added": "2026-05",
     "contribution": "BTC news headlines from 6 free RSS feeds"},
]

# Curated free RSS feeds. BTC-tagged where possible.
FEEDS = [
    ("CoinDesk",            "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("Cointelegraph BTC",   "https://cointelegraph.com/rss/tag/bitcoin"),
    ("Bitcoin Magazine",    "https://bitcoinmagazine.com/.rss/full/"),
    ("Decrypt BTC",         "https://decrypt.co/feed?tag=bitcoin"),
    ("The Block",           "https://www.theblock.co/rss.xml"),
    ("BitcoinNews",         "https://news.bitcoin.com/feed/"),
]

BTC_RE = re.compile(r"\b(btc|bitcoin|satoshi|lightning|halving|hashrate|miner)\b", re.I)


@dataclass
class Headline:
    source: str
    title: str
    link: str
    published: Optional[datetime] = None
    summary: str = ""


@dataclass
class NewsSnapshot:
    headlines: List[Headline] = field(default_factory=list)


def _parse_pubdate(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


def _parse_feed(source: str, xml_text: str, btc_only: bool) -> List[Headline]:
    out: List[Headline] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out

    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for it in items:
        title_el = it.find("title") or it.find("{http://www.w3.org/2005/Atom}title")
        link_el = it.find("link") or it.find("{http://www.w3.org/2005/Atom}link")
        date_el = (
            it.find("pubDate")
            or it.find("{http://purl.org/dc/elements/1.1/}date")
            or it.find("{http://www.w3.org/2005/Atom}updated")
            or it.find("{http://www.w3.org/2005/Atom}published")
        )
        desc_el = it.find("description") or it.find("{http://www.w3.org/2005/Atom}summary")

        title = (title_el.text or "").strip() if title_el is not None else ""
        if link_el is not None:
            link = (link_el.text or link_el.attrib.get("href", "")).strip()
        else:
            link = ""
        published = _parse_pubdate(date_el.text if date_el is not None else None)
        summary = _strip_html(desc_el.text if desc_el is not None and desc_el.text else "")

        if not title:
            continue
        if btc_only and not BTC_RE.search(title + " " + summary):
            continue
        out.append(Headline(source, title, link, published, summary[:280]))
    return out


def fetch_news(per_feed: int = 5, btc_only: bool = True) -> NewsSnapshot:
    snap = NewsSnapshot()
    for source, url in FEEDS:
        xml_text = get_text(url, timeout=8)
        if not xml_text:
            continue
        items = _parse_feed(source, xml_text, btc_only)
        items.sort(key=lambda h: h.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        snap.headlines.extend(items[:per_feed])
    # Global sort newest-first
    snap.headlines.sort(
        key=lambda h: h.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return snap
