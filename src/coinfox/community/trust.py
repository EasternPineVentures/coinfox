"""Local contributor reputation primitives.

This is intentionally non-crypto. The first trust layer for coinfox should be
earned contribution history, maintainer review, and transparent penalties.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


SCORES = {
    "issue_opened": 1,
    "triage_helpful": 2,
    "pr_opened": 2,
    "pr_merged": 10,
    "security_fix": 20,
    "docs_merged": 6,
    "spam": -20,
    "malicious": -100,
    "code_of_conduct": -50,
}


@dataclass(frozen=True)
class ContributionEvent:
    handle: str
    kind: str
    points: int
    created_ts: int
    ref: Optional[str] = None
    note: str = ""

    def as_dict(self) -> Dict[str, object]:
        return {
            "handle": self.handle,
            "kind": self.kind,
            "points": self.points,
            "created_ts": self.created_ts,
            "ref": self.ref,
            "note": self.note,
        }


@dataclass(frozen=True)
class ContributorReputation:
    handle: str
    score: int
    tier: str
    events: int


class ReputationLedger:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, handle: str, kind: str, ref: Optional[str] = None, note: str = "") -> ContributionEvent:
        event = ContributionEvent(
            handle=_normalize_handle(handle),
            kind=kind,
            points=SCORES.get(kind, 0),
            created_ts=int(time.time()),
            ref=ref,
            note=note.strip(),
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.as_dict(), sort_keys=True) + "\n")
        return event

    def events(self) -> List[ContributionEvent]:
        if not self.path.exists():
            return []
        out: List[ContributionEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                out.append(
                    ContributionEvent(
                        handle=_normalize_handle(str(raw["handle"])),
                        kind=str(raw["kind"]),
                        points=int(raw["points"]),
                        created_ts=int(raw["created_ts"]),
                        ref=str(raw["ref"]) if raw.get("ref") is not None else None,
                        note=str(raw.get("note") or ""),
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return out

    def reputation(self, handle: str) -> ContributorReputation:
        normalized = _normalize_handle(handle)
        matching = [event for event in self.events() if event.handle == normalized]
        score = score_events(matching)
        return ContributorReputation(
            handle=normalized,
            score=score,
            tier=tier_for_score(score),
            events=len(matching),
        )


def score_events(events: Iterable[ContributionEvent]) -> int:
    return sum(int(event.points) for event in events)


def tier_for_score(score: int) -> str:
    if score >= 50:
        return "maintainer-track"
    if score >= 20:
        return "trusted"
    if score >= 5:
        return "known"
    if score < 0:
        return "restricted"
    return "new"


def _normalize_handle(handle: str) -> str:
    clean = handle.strip().lower()
    if clean.startswith("@"):
        clean = clean[1:]
    return clean or "unknown"
