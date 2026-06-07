"""Web sources for BTC intel.

Every fetcher here is best-effort: it returns a structured result on success,
or None on failure. The aggregator in `coinfox.intel` calls them in parallel
and stitches the results together. Add new sources by dropping a module here
and registering it in `intel.SOURCES`.
"""

from . import prices, derivatives, onchain, news, social, dev, macro, sentiment, chainlink  # noqa: F401
