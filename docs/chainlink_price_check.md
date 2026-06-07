# Chainlink On-Chain Price Cross-Check

CoinFox reads BTC/USD and ETH/USD directly from **Chainlink Data Feeds** on
Ethereum mainnet and compares them against the median of its CeFi REST prices
(Binance, Coinbase, Kraken, Bitstamp, CoinGecko). The point is a cheap,
**independent, decentralized second opinion**: if a centralized quote is stale,
wrong, or manipulated, the on-chain reference makes it obvious.

> Chainlink is used **read-only**. CoinFox never sends a transaction, spends gas,
> or touches LINK or any token — consistent with CoinFox having no coin, no
> token, and no on-chain settlement. Anything transactional (VRF, CCIP,
> payments) is deliberately **out of scope** for CoinFox and would belong to a
> different product in the ecosystem.

## How it works

- Source module: [src/coinfox/sources/chainlink.py](../src/coinfox/sources/chainlink.py).
- It makes a raw JSON-RPC `eth_call` to each feed aggregator's
  `latestRoundData()` and decodes the ABI response by hand — **no `web3`
  dependency**, keeping CoinFox lean.
- It is **best-effort** like every CoinFox source: on any failure it returns
  `None` and never breaks the rest of the intel gather.
- Results appear in `coinfox intel` under
  *"Chainlink on-chain (decentralized cross-check)"*, including the percentage
  deviation of the on-chain BTC/USD price from the CeFi median.

## Keyless by default

No API key is required — CoinFox calls a public Ethereum RPC endpoint. Public
RPCs are rate-limited and occasionally flaky, so for reliability you can point
CoinFox at your own node or provider:

```bash
# optional — defaults to a keyless public RPC if unset
export COINFOX_ETH_RPC_URL="https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY"
coinfox intel
```

## Feeds

Configured in `FEEDS` in the source module, using Chainlink's published mainnet
aggregator-proxy addresses
(<https://docs.chain.link/data-feeds/price-feeds/addresses>):

| Pair | Aggregator proxy |
|---|---|
| BTC/USD | `0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c` |
| ETH/USD | `0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419` |

Add more by dropping another entry into `FEEDS` with the address from the
Chainlink docs.

## Reading the deviation

The `vs CeFi` column compares on-chain BTC/USD to the CeFi median:

- **green** — within 0.5% (normal)
- **yellow** — 0.5%–2% (worth a glance; one side may be lagging)
- **red** — over 2% (a feed is stale or something is genuinely off)

Chainlink feeds update on their own heartbeat/deviation schedule, so a small,
fluctuating gap during fast moves is expected and not a problem.

Docs: <https://docs.chain.link/data-feeds>
