"""Bitcoin Core development pulse: latest release + recent commits to master."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ._http import get_json

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "source", "added": "2026-05",
     "contribution": "bitcoin/bitcoin release + recent commit pulse"},
]


@dataclass
class Release:
    tag: str
    name: str
    published_at: Optional[str]
    url: str


@dataclass
class Commit:
    sha: str
    message: str
    author: str
    date: Optional[str]
    url: str


@dataclass
class DevSnapshot:
    latest_release: Optional[Release] = None
    recent_commits: List[Commit] = field(default_factory=list)


def fetch_dev(limit_commits: int = 5) -> DevSnapshot:
    snap = DevSnapshot()
    # Latest release
    rel = get_json("https://api.github.com/repos/bitcoin/bitcoin/releases/latest")
    if rel and isinstance(rel, dict):
        try:
            snap.latest_release = Release(
                tag=rel.get("tag_name", ""),
                name=rel.get("name") or rel.get("tag_name", ""),
                published_at=rel.get("published_at"),
                url=rel.get("html_url", ""),
            )
        except (KeyError, TypeError):
            pass
    # Recent commits
    commits = get_json(
        "https://api.github.com/repos/bitcoin/bitcoin/commits",
        params={"per_page": limit_commits},
    )
    if commits and isinstance(commits, list):
        for c in commits:
            try:
                snap.recent_commits.append(Commit(
                    sha=c["sha"][:7],
                    message=(c["commit"]["message"].splitlines()[0])[:160],
                    author=(c["commit"]["author"] or {}).get("name", ""),
                    date=(c["commit"]["author"] or {}).get("date"),
                    url=c.get("html_url", ""),
                ))
            except (KeyError, TypeError, IndexError):
                continue
    return snap
