# CoinFox Mobile

Expo mobile client for the CoinFox public market-intelligence API.

## API Target

The app starts local by default:

```bash
EXPO_PUBLIC_COINFOX_API_URL=http://localhost:8000
```

For a physical phone, `localhost` points at the phone, not the computer. Use the computer LAN address instead:

```bash
EXPO_PUBLIC_COINFOX_API_URL=http://192.168.1.25:8000
```

When the public backend is ready, the intended production target is:

```bash
EXPO_PUBLIC_COINFOX_API_URL=https://api.coinfox.cloud
```

The old `EXPO_PUBLIC_NYFX_API_URL` variable still works as a temporary local fallback, but new setups should use `EXPO_PUBLIC_COINFOX_API_URL`.

## Run

```bash
cd mobile
npm install
Copy-Item .env.example .env
npm run start
```

Start the local API from the repo root:

```bash
python -m coinfox api --host 0.0.0.0 --port 8000
```

For `npm run web`, the FastAPI backend also needs CORS enabled for the Expo origin. Native Expo builds do not use browser CORS.

## Screens

- `Read`: symbol input, major-mover presets, LONG/SHORT/NEUTRAL bias, thesis check, drivers, source health, and feedback.
- `Desk`: community trade-idea feed, prediction buttons, comments, and WebSocket refresh.
- `Post`: symbol, direction, entry, thesis, and reasoning.
- `Account`: stored local identity, reputation, and backend connection state.

CoinFox is educational market intelligence. There is no wallet, token flow, deposit, withdrawal, or live order surface in this client.
