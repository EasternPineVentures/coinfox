# CoinFox Social Links and Feed Plan

CoinFox needs shareable links before it becomes a real trading social surface. The first version should stay simple: a user can share a market read or a setup card, and the recipient lands on the right tab with the right symbol or post opened.

## Terms

- Hyperlink: a clickable URL.
- Direct link: a URL that opens a specific screen or item instead of only the home screen.
- Permalink: a stable direct link to a piece of content, such as a setup post.
- Deep link: a mobile app link, such as `coinfox://post/<post-id>`, that opens the installed app.
- Universal link: an `https` link, such as `https://coinfox.cloud?screen=desk&post=<post-id>`, that can open the app later if the domain is configured for iOS and Android app links.

## Supported First Links

Local web:

```text
http://localhost:8081?screen=read&symbol=BTCUSDT
http://localhost:8081?screen=desk&post=<post-id>
```

Future public web:

```text
https://coinfox.cloud?screen=read&symbol=BTCUSDT
https://coinfox.cloud?screen=desk&post=<post-id>
```

Installed app scheme:

```text
coinfox://read/BTCUSDT
coinfox://post/<post-id>
```

## Mobile Contract

The mobile app should:

- Build share links from `EXPO_PUBLIC_COINFOX_WEB_URL`.
- Fall back to `https://coinfox.cloud` if no web URL is configured.
- Parse incoming read links and switch to the `Read` tab.
- Parse incoming setup links and switch to the `Desk` tab.
- Expand comments for a linked setup when possible.

## Social Template Direction

The current app already matches the simplest useful social template:

- `Read`: live market intelligence panel.
- `Desk`: activity feed with setup cards, predictions, comments, and share links.
- `Post`: setup composer.
- `Account`: local identity and reputation.

The next site layout should keep that shape instead of starting with a generic marketing page:

- Mobile: bottom tabs with `Read`, `Desk`, `Post`, and `Account`.
- Desktop web: left rail for account/watchlist, center feed for setups, right rail for live read and source health.
- Setup cards: symbol, direction, entry, thesis check, target, reasoning, comments, predictions, and a permalink.
- Safety language: never frame a thesis check as an instruction. It is the level where the idea starts to weaken.

## Later Additions

- Public profile pages.
- Followed traders and watchlists.
- Saved setup collections.
- Searchable symbols and tags.
- Moderation queue for spam or unsafe claims.
- Public post pages rendered by the API or web app for clean sharing previews.
- Domain-level universal links for `coinfox.cloud`.
