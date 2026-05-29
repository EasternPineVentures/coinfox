# Contributing to coinfox 🦊

**coinfox is a bastion of free BTC info.** No keys, no paywalls, no tracking.
If you can pull BTC data from somewhere on the open web, you can add it here
and the whole community benefits.

## Ways to help

- 🔌 **Add a new data source** (easiest — see below)
- 🧠 **Improve the probability model** (`src/coinfox/model.py`)
- 🎨 **Polish the dashboard** (`src/coinfox/dashboard.py`)
- 🐛 **Fix a bug** or **report one** via Issues
- 📚 **Improve docs** — README, examples, screenshots

## Project values

1. **Free**. Sources must be usable without API keys for the default install.
   (Optional keyed sources can be added but must degrade gracefully.)
2. **Resilient**. A single dead endpoint must never break the whole tool.
3. **Transparent**. Every signal in the model is human-readable. No black boxes.
4. **Not financial advice**. We surface info. Humans make decisions.

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/coinfox.git
cd coinfox
pip install -r requirements.txt
python -m coinfox intel
```

## Add a new data source (5 minutes)

Every source is a small module under `src/coinfox/sources/`. Pattern:

```python
# src/coinfox/sources/my_source.py
from dataclasses import dataclass
from typing import Optional
from ._http import get_json

@dataclass
class MySnapshot:
    something: Optional[float] = None

def fetch_my_source() -> MySnapshot:
    snap = MySnapshot()
    d = get_json("https://api.example.com/btc")
    if not d:
        return snap                          # return empty on failure — never raise
    try:
        snap.something = float(d["value"])
    except (KeyError, ValueError, TypeError):
        pass
    return snap
```

Then register it in `src/coinfox/intel.py`:

```python
from .sources import my_source

SOURCES = {
    ...,
    "my_source": my_source.fetch_my_source,
}
```

And add a small render block in `src/coinfox/dashboard.py::render_intel`.

That's it. The aggregator runs every source in parallel and isolates failures.

### Source ideas the community wants

- ETF flow proxies (Bitwise / Farside scraping)
- Liquidation heatmap (Coinglass alternative)
- Lightning Network capacity (mempool.space `/api/v1/lightning/statistics/latest`)
- Hashrate distribution by pool (mempool.space)
- Stablecoin supply (DeFiLlama)
- Exchange netflows (CryptoQuant free tier)
- Google Trends for "bitcoin"
- Long/short ratio (Binance, Bybit)
- Options skew/IV (Deribit)
- More news sources, podcasts, YouTube creators (RSS)
- Translate news titles to other languages

Open an Issue first if you're not sure whether something fits.

## Code style

- Python 3.9+
- Standard library where possible; only `requests` and `rich` as runtime deps.
- Type hints encouraged but not enforced.
- Keep functions small; prefer composition over inheritance.
- No new dependencies without an issue discussion first.

## Tests

There aren't many yet — `python -m coinfox intel` is the smoke test.
Contributions that add `pytest`-based unit tests are very welcome,
especially for `indicators.py` and `model.py` (pure functions, easy to test).

## Pull request checklist

- [ ] Code follows existing patterns
- [ ] No new required dependencies (or discussed in an issue)
- [ ] `python -m coinfox` and `python -m coinfox intel` still run
- [ ] README / CONTRIBUTING updated if you changed user-facing behavior
- [ ] You've stated where the data comes from and confirmed the source's ToS allows this use

## Code of Conduct

Be kind. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

By contributing, you agree your contributions are licensed under the MIT License.
