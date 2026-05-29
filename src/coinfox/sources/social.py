"""Social signal: top posts from r/Bitcoin (public .json endpoint)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ._http import get_json

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "source", "added": "2026-05",
     "contribution": "r/Bitcoin hot posts via public reddit JSON"},
]


@dataclass
class RedditPost:
    title: str
    score: int
    num_comments: int
    permalink: str
    flair: Optional[str] = None
    created_utc: Optional[float] = None


@dataclass
class SocialSnapshot:
    top_posts: List[RedditPost] = field(default_factory=list)


def fetch_reddit(subreddit: str = "Bitcoin", limit: int = 10, listing: str = "hot") -> SocialSnapshot:
    snap = SocialSnapshot()
    # Reddit requires a real user-agent. Their public JSON works without auth for read-only.
    d = get_json(
        f"https://www.reddit.com/r/{subreddit}/{listing}.json",
        params={"limit": limit, "raw_json": 1},
        headers={"User-Agent": "coinfox/0.2 (research)"},
    )
    if not d:
        return snap
    try:
        children = d["data"]["children"]
    except (KeyError, TypeError):
        return snap
    for c in children:
        try:
            p = c["data"]
            if p.get("stickied"):
                continue
            snap.top_posts.append(RedditPost(
                title=p.get("title", "")[:200],
                score=int(p.get("score", 0)),
                num_comments=int(p.get("num_comments", 0)),
                permalink="https://reddit.com" + p.get("permalink", ""),
                flair=p.get("link_flair_text"),
                created_utc=p.get("created_utc"),
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return snap
