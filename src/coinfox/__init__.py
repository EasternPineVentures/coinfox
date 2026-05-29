"""coinfox — a fox that watches BTC and estimates the odds."""

try:
    from dotenv import load_dotenv as _load
    _load()  # loads .env from cwd or any parent — silent if not found
except ImportError:
    pass  # python-dotenv not installed; env vars must be set manually

__version__ = "0.2.0"

CONTRIBUTORS = [
    {"name": "Brendan", "github": "EasternPineVentures", "role": "founder",
     "added": "2026-05",
     "contribution": "started coinfox; built the watcher, the call, and the source framework"},
]
