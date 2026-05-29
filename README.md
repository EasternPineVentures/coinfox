# coinfox 🦊

> **A bastion of free BTC info.** No keys. No paywalls. No tracking.
> A fox in your terminal that watches Bitcoin from everywhere on the open web,
> thinks out loud, and tells you the odds.

```
        /\___/\
       (  o o  )    < watching BTC...
       (  =^=  )
        (______)
```

[![CI](https://github.com/EasternPineVentures/coinfox/actions/workflows/ci.yml/badge.svg)](https://github.com/EasternPineVentures/coinfox/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## Why

Most BTC tooling is either locked behind paid APIs or trying to sell you
something. **coinfox is the opposite**: a community-owned, MIT-licensed
terminal tool that pulls free BTC information from everywhere on the web
and surfaces it in one place — with a transparent probability model and
an actionable trade idea you can second-guess.

You should grow with us. Add a source. Tune a weight. Open a PR.

## What it does

### `coinfox watch` — the signal verdict
EMA stack, RSI, MACD, Bollinger %B, volume z-score, Fear & Greed, optional
derivatives funding & basis → a single **P(up)** with a **confidence** score.

### `coinfox call` — the actionable call
Turns the verdict into entry / stop / target / R:R and a **suggested
position size** (capped quarter-Kelly, gated by confidence). Built to help
you *think clearly* — not to YOLO.

### `coinfox intel` — the firehose
Everything we know about BTC right now, gathered in parallel from:

| Category      | Sources |
|---------------|---------|
| Spot prices   | Binance · Coinbase · Kraken · Bitstamp · CoinGecko |
| Global market | CoinGecko (mcap, dominance, volume) |
| Derivatives   | Binance · Bybit · OKX · Deribit (funding, OI, basis) |
| On-chain      | mempool.space · blockchain.info (fees, hashrate, halving) |
| Sentiment     | alternative.me Fear & Greed (+ 30d) · CoinGecko community |
| News          | CoinDesk · Cointelegraph · Bitcoin Magazine · Decrypt · The Block · news.bitcoin.com |
| Social        | r/Bitcoin top posts |
| Dev           | bitcoin/bitcoin releases & recent commits |
| Macro         | DXY · Gold · Silver · WTI · Brent · S&P 500 · US10Y (Stooq) |

All keyless. All free. Any source failing degrades gracefully.

### `coinfox all` — everything
Verdict + Call + Intel, one go.

## Install

```bash
git clone https://github.com/EasternPineVentures/coinfox.git
cd coinfox
pip install -r requirements.txt
```

## Use

```bash
# Quick verdict on the 1h chart
python -m coinfox

# Actionable trade idea (entry/stop/target/size)
python -m coinfox call

# Use derivatives (funding + basis) in the model too
python -m coinfox call --use-derivs

# Different timeframe / horizon
python -m coinfox call -t 4h --horizon 6

# The full firehose
python -m coinfox intel

# Everything together
python -m coinfox all

# Live refresh
python -m coinfox watch --watch-loop --interval 30

# 🦊 See who built what (the Hall of Foxes)
python -m coinfox credits

# 🔌 Scaffold a new source — your name is auto-credited
python -m coinfox new-source my-source --author your_handle
```

## How the probability is built

A transparent weighted-confluence model. Each signal votes in `[-1, +1]` with
an explicit weight. Votes get summed, squashed through a logistic, and
reported as `P(up over the next N candles)`. **Confidence** reflects
agreement across signals — low confidence = signals disagree, take it lightly.

Read every line in [`src/coinfox/model.py`](src/coinfox/model.py). Tweak it.
PR a better one.

## How the call is built

From the verdict, [`src/coinfox/trade.py`](src/coinfox/trade.py) computes:

- **Stop** at `1.5 × ATR(14)` against the bias
- **Target** at `2.5 × ATR(14)` in favor
- **R:R** = reward / risk
- **Size** = `quarter-Kelly × confidence`, **capped at 2% of bankroll**
- **Gate**: refuses to call a setup if edge < 6%, confidence < 35%, or R:R < 1

So even when probability looks juicy, if signals disagree you'll get
**STAND ASIDE**. The fox would rather miss a trade than chase a bad one.

## Not financial advice

`coinfox` is an **experimental, educational tool**. It surfaces public info
and applies a transparent heuristic. It does not know your tax situation,
your bankroll, your conviction, or the news that breaks five seconds from now.

The call feature exists to help you think — entry, stop, R:R, and a size
that won't blow you up — but **you** pull the trigger and **you** own the
outcome. Don't risk money you can't afford to lose.

## Roadmap

- [ ] Backtest harness for the model
- [ ] More sources (ETF flows, liquidation maps, Lightning, options skew)
- [ ] JSON output mode for piping into other tools
- [ ] Webhook / Discord / Telegram notifier
- [ ] Multi-coin support (ETH, then community choice)

## Join us 🦊

> **Every contributor gets credit, by name, forever.** Your handle goes into
> the source you wrote, shows up in `coinfox credits` (the Hall of Foxes),
> and appears in the footer of every `coinfox intel` run that uses your data.

The fastest path from "I have an idea" to "I'm a credited contributor":

```bash
python -m coinfox new-source liquidations --author your_handle \
    --endpoint https://api.example.com/liquidations \
    --why "track forced selling to spot panic bottoms"
```

That command:
1. Drops a working stub at `src/coinfox/sources/liquidations.py` with your
   name already in the `CONTRIBUTORS` list.
2. Auto-registers it in the intel aggregator so it runs in parallel with
   every other source.
3. Tells you the next 4 steps to ship a PR.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide and
[CONTRIBUTORS.md](CONTRIBUTORS.md) for the Hall of Foxes.

Other ways to be featured:
- 🧠 **Tune the probability model** (`src/coinfox/model.py`)
- 🎨 **Polish the dashboard** (`src/coinfox/dashboard.py`)
- 📚 **Improve docs**, add examples, ship screenshots
- 🐛 **Report bugs**, **review PRs**, **help triage Issues**

All contribution types (`source`, `indicator`, `model`, `ui`, `docs`) are
shown side-by-side in the credits view.

**Free BTC info, for everyone, forever.** That's the whole point.

## License

MIT © coinfox contributors
