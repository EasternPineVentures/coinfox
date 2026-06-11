/**
 * Social sign-in configuration.
 *
 * Google is the only provider wired up for now (Apple + Facebook come later —
 * they'll slot in beside this with the same shape).
 *
 * HOW TO FILL THIS IN (one time):
 *   1. Go to https://console.cloud.google.com/apis/credentials
 *   2. Create OAuth client IDs for the platforms you test on:
 *        - iOS         → bundle id  com.easternpineventures.coinfox
 *        - Android     → package    com.easternpineventures.coinfox  (+ SHA-1 from your dev build)
 *        - Web         → used as the fallback / for the backend audience check
 *   3. Paste each client ID below.
 *   4. Put the SAME ids (comma-separated) in the API's GOOGLE_CLIENT_ID env var
 *      so the backend will accept tokens minted for them.
 *
 * Leave a value as "" if you don't have that platform's id yet — the Google
 * button stays disabled until at least one is present, so nothing breaks.
 */
export const GOOGLE_CLIENT_IDS = {
  ios: "",
  android: "",
  web: "",
} as const;

/** True once at least one Google client id has been filled in above. */
export const isGoogleConfigured =
  GOOGLE_CLIENT_IDS.ios !== "" ||
  GOOGLE_CLIENT_IDS.android !== "" ||
  GOOGLE_CLIENT_IDS.web !== "";
