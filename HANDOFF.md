# CoinFox — HANDOFF (give this to any AI to get the rundown fast)

**Last updated:** 2026-06-10 · **Owner:** fox1i (Eastern Pine Ventures)
**How to use:** Read this first, then continue. Update it (esp. sections 2–4) at the end of each session.

## 0. ▶️ PROMPT FOR THE NEXT SESSION
> You're picking up **CoinFox**, a phone-first social platform for trading (repo: `C:\Users\fox1i\Documents\GitHub\coinfox`). Read this HANDOFF, then continue from section 4. We were mid-way through **Google sign-in** (dev build is running on fox1i's Android phone). Verify backend with `PYTHONPATH=src python -m pytest tests/test_social_api.py -q` (26 passing) and mobile with `cd mobile && npx tsc --noEmit`. When you stop, update this file.

## 1. What CoinFox is
The first **social** platform for trading — social-media FIRST, trading second. A proof-ranked FYP feed where people who are actually *right* rise. Free-form **Discussion** posts sit alongside structured **Trade calls**; trading is the foundation, not a hard "everything must be a trade" stop. Nothing forced/trade-pushy (also lowers "financial advice" legal exposure). **No coin, no token.** Gold = play-money arena (NYFE) only.

## 2. Architecture
- **Backend**: FastAPI in `src/coinfox/api.py`; social store `src/coinfox/community/social.py` (SQLite at `~/.coinfox/social.sqlite`). Tests: `tests/test_social_api.py`.
- **Mobile**: Expo app, single `mobile/App.tsx` (~110KB, all screens inline). **Dev build** (not Expo Go — OAuth needs it). Tabs: Feed · Watch · NYFE · Research · Account (Post = top compose bar on Feed).
- **Live data**: `data.fetch_spot()` (Binance→Coinbase, US-friendly, symbol-safe) + `GET /api/price/{symbol}`.
- **Scripts**: `scripts/seed_demo.py` (believable demo community; never deletes users), `scripts/resolve_calls.py` (auto-resolve open calls vs live price).

## 3. What's built (Lane B)
Proof-ranked feed (`list_feed_ranked`, open calls + discussions only — resolved calls leave the feed), author proof badge (`author_track_record`), call resolution + predictor credit, Reddit-style **votes** on posts AND comments (optimistic + live WS sync), **top community reply** surfaced on each card, free-form **discussions**, Research tab with intent guide, lean feed + top compose bar, **Accounts Phase 1** (browse as guest; sign in to act; claim a unique handle). Trade cards softened (reasoning leads, jargon hidden, predict reframed as a friendly poll).

## 4. IN PROGRESS — Google sign-in (Phase 2)
- ✅ Backend: `auth_identities` table, `find_or_create_oauth_user`, `POST /api/auth/google` (verifies Google ID token; accepts multiple auds via `GOOGLE_CLIENT_ID` env CSV). Mobile `authGoogle()` client added. `expo-auth-session`/`expo-dev-client`/`expo-web-browser`/`expo-crypto` installed; `eas.json` dev profile; scheme `coinfox`, pkg `com.easternpineventures.coinfox`.
- ⏳ TODO: fox1i to provide **Web client ID** + **Android client ID** (Android client needs SHA-1 from `eas credentials`). Then: set API `GOOGLE_CLIENT_ID=web,android`, wire `expo-auth-session/providers/google` "Continue with Google" button into AccountGate, hot-reload + test.
- **Phase 2b**: Apple/Facebook/GitHub/TikTok after Google works.

## 5. Run it
- API: `PYTHONPATH=src python -m uvicorn coinfox.api:app --host 0.0.0.0 --port 8000`
- Mobile (dev build): `cd mobile && npx expo start --dev-client` (phone + PC same Wi-Fi; `mobile/.env` points at LAN IP, currently `10.0.0.200:8000`)
- Seed demo data: `PYTHONPATH=src python scripts/seed_demo.py`

## 6. Guardrails / principles
Social-first, never forced, high-craft (avoid the "cheap AI / overwhelming" look). No coin/token. Not investment advice.
