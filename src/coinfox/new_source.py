"""`coinfox new-source` — scaffold a new source module with attribution baked in.

Drops a working stub at `src/coinfox/sources/<name>.py` with the contributor
already credited, registers it in `intel.py`, and prints next steps.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional

TEMPLATE = '''"""{title} — community-contributed BTC source.

Endpoint(s): {endpoint}
Why it matters: {why}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ._http import get_json

CONTRIBUTORS = [
    {{"name": "{author_name}", "github": "{author_handle}", "role": "source",
     "added": "{ym}",
     "contribution": "{contribution}"}},
]


@dataclass
class {camel}Snapshot:
    # TODO: define the fields you parse out of the response
    value: Optional[float] = None
    raw: dict = field(default_factory=dict)


def fetch_{snake}() -> {camel}Snapshot:
    """Fetch {title}. Return an empty snapshot on any failure — never raise."""
    snap = {camel}Snapshot()
    data = get_json("{endpoint}")
    if not data:
        return snap
    try:
        # TODO: parse `data` into `snap`
        snap.raw = data if isinstance(data, dict) else {{"data": data}}
    except (KeyError, ValueError, TypeError):
        pass
    return snap
'''


def _slug(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_").lower()
    if not name:
        raise ValueError("invalid name")
    return name


def _camel(name: str) -> str:
    return "".join(p.title() for p in _slug(name).split("_"))


def scaffold(name: str, author_handle: str, author_name: Optional[str] = None,
             endpoint: str = "https://api.example.com/btc",
             why: str = "TODO: what does this tell us about BTC?",
             contribution: Optional[str] = None,
             package_root: Optional[Path] = None) -> Path:
    snake = _slug(name)
    camel = _camel(name)
    author_name = author_name or author_handle
    contribution = contribution or f"{name}: new BTC source"

    root = package_root or Path(__file__).resolve().parent
    sources_dir = root / "sources"
    target = sources_dir / f"{snake}.py"
    if target.exists():
        raise FileExistsError(f"{target} already exists")

    target.write_text(TEMPLATE.format(
        title=name,
        endpoint=endpoint,
        why=why,
        author_name=author_name,
        author_handle=author_handle,
        ym=date.today().strftime("%Y-%m"),
        contribution=contribution,
        camel=camel,
        snake=snake,
    ), encoding="utf-8")

    # Auto-register in sources/__init__.py
    init_path = sources_dir / "__init__.py"
    init = init_path.read_text(encoding="utf-8")
    if snake not in init:
        new_line = init.rstrip().replace(
            "from . import",
            f"from . import {snake},",
            1,
        )
        if new_line == init.rstrip():
            # Fallback: append a plain import
            new_line = init.rstrip() + f"\nfrom . import {snake}  # noqa: F401\n"
        else:
            new_line += "\n"
        init_path.write_text(new_line, encoding="utf-8")

    # Auto-register in intel.py's SOURCES dict
    intel_path = root / "intel.py"
    intel = intel_path.read_text(encoding="utf-8")
    if f"\"{snake}\":" not in intel:
        import_line = f"from .sources import {snake}\n"
        if import_line not in intel:
            intel = intel.replace(
                "from .sources import",
                f"from .sources import {snake},",
                1,
            )
        entry = f'    "{snake}":        {snake}.fetch_{snake},\n'
        intel = intel.replace("SOURCES = {", "SOURCES = {\n" + entry, 1)
        # collapse the accidental double newline introduced above
        intel = intel.replace("SOURCES = {\n\n" + entry, "SOURCES = {\n" + entry, 1)
        intel_path.write_text(intel, encoding="utf-8")

    return target
