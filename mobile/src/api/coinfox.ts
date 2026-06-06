import type {
  Comment,
  Direction,
  ExchangeBoard,
  ExchangePosition,
  ExchangeSession,
  ExchangeStats,
  FeedMessage,
  PredictionOutcome,
  TradePost,
  TradePostDraft,
  User,
  VoteDirection
} from "../types";

const configuredApiUrl = process.env.EXPO_PUBLIC_COINFOX_API_URL
  || process.env.EXPO_PUBLIC_NYFX_API_URL
  || "http://localhost:8000";

export const API_URL = configuredApiUrl.replace(/\/$/, "");

export type BiasDirection = "LONG" | "SHORT" | "NEUTRAL";
export type BiasDriver = {
  name: string;
  impact: string;
  plain_english: string;
  lean?: string;
  contribution?: number;
  detail?: string;
};
export type BiasInvalidation = {
  type?: string;
  label: string;
  level?: number | null;
  reason: string;
  not_a_stop_loss: boolean;
};
export type BiasSourceHealth = {
  status?: string;
  stale_sources?: string[];
  notes?: string[];
};
export type BiasRead = {
  symbol: string;
  bias: BiasDirection;
  conviction?: number;
  confidence?: number;
  probability_up?: number;
  probability_down?: number;
  thesis?: string;
  human_readable?: string;
  invalidation?: BiasInvalidation | null;
  drivers?: BiasDriver[];
  source_health?: BiasSourceHealth | string;
  price?: number | null;
  change_24h_pct?: number | null;
  regime_hint?: string;
  timestamp?: string;
  updated_at?: string;
};
export type BiasFeedbackPayload = {
  anonymous_user_id: string;
  symbol: string;
  bias_shown: BiasDirection;
  confidence_shown?: number;
  user_action: string;
  user_invalidation_level?: number | null;
  comment?: string;
};

type RequestOptions = RequestInit & {
  userId?: string | null;
};

class CoinFoxApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "CoinFoxApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (options.userId) {
    headers.set("x-user-id", options.userId);
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers
  });

  const contentType = res.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in payload
      ? String(payload.detail)
      : `Request failed with status ${res.status}`;
    throw new CoinFoxApiError(res.status, detail);
  }
  return payload as T;
}

export function suggestUsernames(count = 5): Promise<string[]> {
  return request<{ suggestions: string[] }>(`/api/username/suggest?count=${count}`).then(
    (payload) => payload.suggestions
  );
}

export function createUser(username: string): Promise<User> {
  return request<User>("/api/users", {
    method: "POST",
    body: JSON.stringify({ username })
  });
}

export function getUser(userId: string): Promise<User> {
  return request<User>(`/api/users/${encodeURIComponent(userId)}`);
}

export function listPosts(userId: string, limit = 50): Promise<TradePost[]> {
  return request<TradePost[]>(`/api/posts?limit=${limit}`, { userId });
}

export function createPost(userId: string, draft: TradePostDraft): Promise<TradePost> {
  return request<TradePost>("/api/posts", {
    method: "POST",
    userId,
    body: JSON.stringify(draft)
  });
}

export function predictOutcome(
  userId: string,
  postId: string,
  predictedOutcome: PredictionOutcome
): Promise<{ message: string }> {
  return request<{ message: string }>(`/api/posts/${encodeURIComponent(postId)}/predict`, {
    method: "POST",
    userId,
    body: JSON.stringify({ predicted_outcome: predictedOutcome })
  });
}

export function votePost(
  userId: string,
  postId: string,
  direction: VoteDirection
): Promise<{ post_id: string; score: number; viewer_vote: "boost" | "fade" | null }> {
  return request(`/api/posts/${encodeURIComponent(postId)}/vote`, {
    method: "POST",
    userId,
    body: JSON.stringify({ direction })
  });
}

export function listComments(postId: string): Promise<Comment[]> {
  return request<Comment[]>(`/api/posts/${encodeURIComponent(postId)}/comments`);
}

export function addComment(userId: string, postId: string, content: string): Promise<Comment> {
  return request<Comment>(`/api/posts/${encodeURIComponent(postId)}/comments`, {
    method: "POST",
    userId,
    body: JSON.stringify({ content })
  });
}

export function getBias(symbol: string): Promise<BiasRead> {
  return request<BiasRead>(`/bias?symbol=${encodeURIComponent(symbol.trim().toUpperCase() || "BTCUSDT")}`);
}

export function submitBiasFeedback(payload: BiasFeedbackPayload): Promise<{ ok: boolean; id: number }> {
  return request<{ ok: boolean; id: number }>("/feedback", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getExchange(userId: string, status?: "open" | "closed"): Promise<ExchangeBoard> {
  const query = status ? `?status=${status}` : "";
  return request<ExchangeBoard>(`/api/exchange/positions${query}`, { userId });
}

export function openPosition(
  userId: string,
  symbol: string,
  direction: Direction,
  amount: number
): Promise<ExchangePosition> {
  return request<ExchangePosition>("/api/exchange/positions", {
    method: "POST",
    userId,
    body: JSON.stringify({ symbol: symbol.trim().toUpperCase(), direction, amount })
  });
}

export function closePosition(userId: string, positionId: number): Promise<ExchangePosition> {
  return request<ExchangePosition>(`/api/exchange/positions/${positionId}/close`, {
    method: "POST",
    userId
  });
}

export function getExchangeSession(): Promise<ExchangeSession> {
  return request<ExchangeSession>("/api/exchange/session");
}

export function getLeaderboard(limit = 10): Promise<ExchangeStats[]> {
  return request<{ leaders: ExchangeStats[] }>(`/api/exchange/leaderboard?limit=${limit}`).then(
    (payload) => payload.leaders
  );
}

export function feedWebSocketUrl(): string {
  const url = new URL(API_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/feed";
  url.search = "";
  return url.toString();
}

export type { FeedMessage };
