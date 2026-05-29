"""Contributor attribution registry.

Every source, indicator, or model improvement should carry credit.
Modules declare a module-level `CONTRIBUTORS` list, like:

    CONTRIBUTORS = [
        {"name": "Brendan", "github": "EasternPineVentures", "role": "founder",
         "added": "2026-05", "contribution": "spot prices across 5 exchanges"},
    ]

The aggregator in `coinfox.credits` walks the package and collects them
for the `coinfox credits` command and the dashboard byline.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Contribution:
    name: str                # display name
    github: Optional[str]    # github handle (no @)
    role: str                # "source", "indicator", "model", "ui", "docs", "founder"
    module: str              # e.g. "coinfox.sources.prices"
    contribution: str        # human-readable description
    added: str = ""          # YYYY-MM


@dataclass
class CreditBook:
    by_contributor: Dict[str, List[Contribution]] = field(default_factory=dict)
    all: List[Contribution] = field(default_factory=list)

    def add(self, c: Contribution) -> None:
        self.all.append(c)
        self.by_contributor.setdefault(c.github or c.name, []).append(c)

    @property
    def contributor_count(self) -> int:
        return len(self.by_contributor)


def _walk_package(pkg) -> List:
    mods = []
    for _, modname, _ in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        try:
            mods.append(importlib.import_module(modname))
        except Exception:
            continue
    mods.append(pkg)
    return mods


def collect() -> CreditBook:
    """Scan the coinfox package for module-level CONTRIBUTORS lists."""
    import coinfox  # local import to avoid cycles
    book = CreditBook()
    for mod in _walk_package(coinfox):
        contribs = getattr(mod, "CONTRIBUTORS", None)
        if not contribs:
            continue
        for entry in contribs:
            try:
                book.add(Contribution(
                    name=entry["name"],
                    github=entry.get("github"),
                    role=entry.get("role", "source"),
                    module=mod.__name__,
                    contribution=entry.get("contribution", ""),
                    added=entry.get("added", ""),
                ))
            except (KeyError, TypeError):
                continue
    # sort: founders first, then by added date desc, then alpha
    role_order = {"founder": 0, "model": 1, "source": 2, "indicator": 3, "ui": 4, "docs": 5}
    book.all.sort(key=lambda c: (role_order.get(c.role, 9), -ord(c.added[0]) if c.added else 0, c.name.lower()))
    return book


def byline(module_name: str) -> str:
    """Quick one-line byline for a module, used in the dashboard."""
    try:
        mod = importlib.import_module(module_name)
    except ImportError:
        return ""
    contribs = getattr(mod, "CONTRIBUTORS", None) or []
    names = []
    for c in contribs:
        handle = c.get("github")
        names.append(f"@{handle}" if handle else c.get("name", ""))
    return " · ".join(names)
