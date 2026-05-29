# NY Fox Exchange Mobile

Expo mobile client for the New York Fox Exchange backend.

## Run

```bash
cd mobile
npm install
Copy-Item .env.example .env
npm run start
```

Set `EXPO_PUBLIC_NYFX_API_URL` to the FastAPI host your phone can reach. For a physical device, `localhost` points at the phone, so use the computer LAN address, for example:

```bash
EXPO_PUBLIC_NYFX_API_URL=http://192.168.1.25:8000
```

For `npm run web`, the FastAPI backend also needs CORS enabled for the Expo origin. Native Expo builds do not use browser CORS.

## Screens

- `Read`: any-symbol input, major-mover presets, LONG/SHORT/NEUTRAL bias, up/down read, buy/sell zone, overhead map, micro details, and position assist.
- `Desk`: live trade feed, prediction buttons, comments, and WebSocket refresh.
- `Post`: symbol, direction, entry, stop, target, and reasoning.
- `Account`: stored trader identity, Gold reputation, and backend connection state.

Gold is displayed only as reputation. There is no wallet, token flow, or deposit/withdraw surface in this client.

The `Read` tab uses the latest unresolved setup for the selected symbol. It includes curated gravity-well assets such as SPY, QQQ, IWM, NVDA, BTC, DXY, US10Y, gold, and oil, while still accepting any typed symbol. When the backend adds richer market-analysis fields, the same screen can be wired to EMA/RSI/MACD/Bollinger/news payloads without changing the core app flow.

Internal intelligence from other systems should flow into generic model/context fields. The mobile UI should keep Foxcoin as the product voice and avoid directly promoting upstream projects this early.
