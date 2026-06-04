"""CLI entry point: `python -m coinfox`.

All logic lives in `coinfox.cli`.  This file is intentionally thin so that
``python -m coinfox`` continues to work without importing the full CLI graph
at module level.
"""

from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
