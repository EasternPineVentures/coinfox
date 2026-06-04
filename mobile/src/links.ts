const DEFAULT_PUBLIC_WEB_URL = "https://coinfox.cloud";

type MaybeWindow = {
  location?: {
    href?: string;
    origin?: string;
    pathname?: string;
  };
};

type MaybeGlobal = typeof globalThis & {
  window?: MaybeWindow;
};

export type DirectLinkTarget =
  | {
      screen: "read";
      symbol: string;
    }
  | {
      screen: "desk";
      postId?: string;
    };

export function getShareBaseUrl(): string {
  const configuredUrl = process.env.EXPO_PUBLIC_COINFOX_WEB_URL?.trim();
  if (configuredUrl) {
    return cleanBaseUrl(configuredUrl);
  }

  const windowLocation = (globalThis as MaybeGlobal).window?.location;
  if (windowLocation?.origin) {
    const path = windowLocation.pathname && windowLocation.pathname !== "/" ? windowLocation.pathname : "";
    return cleanBaseUrl(`${windowLocation.origin}${path}`);
  }

  return DEFAULT_PUBLIC_WEB_URL;
}

export function currentWebUrl(): string | null {
  return (globalThis as MaybeGlobal).window?.location?.href || null;
}

export function buildReadShareUrl(symbol: string): string {
  return appendQueryParams(getShareBaseUrl(), {
    screen: "read",
    symbol: normalizeSymbol(symbol)
  });
}

export function buildPostShareUrl(postId: string): string {
  return appendQueryParams(getShareBaseUrl(), {
    screen: "desk",
    post: postId.trim()
  });
}

export function parseCoinFoxDirectLink(urlText?: string | null): DirectLinkTarget | null {
  const rawUrl = urlText?.trim();
  if (!rawUrl) return null;

  const query = parseQueryParams(rawUrl);
  const schemeTarget = parseSchemeLink(rawUrl, query);
  if (schemeTarget) return schemeTarget;

  const postId = firstNonEmpty(query.post, query.postId, query.setup);
  if (postId) {
    return { screen: "desk", postId };
  }

  const screen = firstNonEmpty(query.screen, query.tab)?.toLowerCase();
  if (screen === "read") {
    return { screen: "read", symbol: normalizeSymbol(query.symbol || "BTCUSDT") };
  }
  if (screen === "desk") {
    return { screen: "desk" };
  }

  const [firstSegment, secondSegment] = pathSegments(rawUrl);
  if (firstSegment === "read") {
    return { screen: "read", symbol: normalizeSymbol(secondSegment || query.symbol || "BTCUSDT") };
  }
  if (firstSegment === "post" || firstSegment === "setup") {
    return secondSegment ? { screen: "desk", postId: secondSegment } : { screen: "desk" };
  }
  if (firstSegment === "desk") {
    return secondSegment ? { screen: "desk", postId: secondSegment } : { screen: "desk" };
  }

  return null;
}

function parseSchemeLink(urlText: string, query: Record<string, string>): DirectLinkTarget | null {
  const match = urlText.match(/^coinfox:\/\/([^/?#]+)(?:\/([^?#]+))?/i);
  if (!match) return null;

  const host = decodeValue(match[1] || "").toLowerCase();
  const pathValue = decodeValue(match[2] || "");
  if (host === "read") {
    return { screen: "read", symbol: normalizeSymbol(pathValue || query.symbol || "BTCUSDT") };
  }
  if (host === "post" || host === "setup") {
    return pathValue ? { screen: "desk", postId: pathValue } : { screen: "desk" };
  }
  if (host === "desk") {
    const postId = pathValue || firstNonEmpty(query.post, query.postId, query.setup);
    return postId ? { screen: "desk", postId } : { screen: "desk" };
  }

  return null;
}

function cleanBaseUrl(value: string): string {
  return value.trim().replace(/[?#].*$/, "").replace(/\/$/, "") || DEFAULT_PUBLIC_WEB_URL;
}

function appendQueryParams(baseUrl: string, params: Record<string, string>): string {
  const query = Object.entries(params)
    .filter(([, value]) => value.trim().length > 0)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join("&");
  return `${cleanBaseUrl(baseUrl)}?${query}`;
}

function parseQueryParams(urlText: string): Record<string, string> {
  const queryIndex = urlText.indexOf("?");
  if (queryIndex === -1) return {};

  const queryText = urlText.slice(queryIndex + 1).split("#")[0] || "";
  return queryText.split("&").reduce<Record<string, string>>((params, pair) => {
    if (!pair) return params;
    const [rawKey = "", rawValue = ""] = pair.split("=");
    const key = decodeValue(rawKey);
    if (!key) return params;
    params[key] = decodeValue(rawValue);
    return params;
  }, {});
}

function pathSegments(urlText: string): string[] {
  const withoutQuery = urlText.split("?")[0]?.split("#")[0] || "";
  const withoutScheme = withoutQuery.replace(/^[a-z][a-z0-9+.-]*:\/\//i, "");
  const firstSlash = withoutScheme.indexOf("/");
  if (firstSlash === -1) return [];
  return withoutScheme
    .slice(firstSlash + 1)
    .split("/")
    .map(decodeValue)
    .filter(Boolean);
}

function normalizeSymbol(value: string): string {
  return value.trim().toUpperCase() || "BTCUSDT";
}

function firstNonEmpty(...values: Array<string | undefined>): string | undefined {
  return values.map((value) => value?.trim()).find((value): value is string => Boolean(value));
}

function decodeValue(value: string): string {
  try {
    return decodeURIComponent(value.replace(/\+/g, " "));
  } catch {
    return value;
  }
}
