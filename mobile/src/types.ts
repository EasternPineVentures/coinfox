export type Direction = "long" | "short";
export type PredictionOutcome = "tp_hit" | "sl_hit";

export type VoteDirection = "boost" | "fade" | "clear";

export type User = {
  id: string;
  username: string;
  gold: number;
  total_predictions: number;
  correct_predictions: number;
  trust_level: number;
  reputation: number;
  created_at: string;
};

export type TrackRecord = {
  resolved_calls: number;
  winning_calls: number;
  call_win_rate: number | null;
  prediction_accuracy: number | null;
  reputation: number;
  gold: number;
  credibility: number;
};

export type PostKind = "call" | "discussion";

export type TradePost = {
  id: string;
  kind?: PostKind;
  title?: string | null;
  body?: string | null;
  user: User;
  track_record?: TrackRecord | null;
  rank_score?: number;
  symbol: string;
  direction: Direction;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  reasoning?: string | null;
  chart_image_url?: string | null;
  created_at: string;
  expires_at: string;
  resolved: boolean;
  outcome?: PredictionOutcome | "expired" | null;
  foxtrot_score?: number | null;
  regime?: string | null;
  confidence?: number | null;
  prediction_stats?: {
    tp_predictions: number;
    sl_predictions: number;
  } | null;
  user_prediction?: PredictionOutcome | null;
  score?: number;
  viewer_vote?: "boost" | "fade" | null;
  comment_count?: number;
  top_comment?: { username: string; content: string; score: number } | null;
};

export type TradePostDraft = {
  symbol: string;
  direction: Direction;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  reasoning?: string;
  chart_image_url?: string;
};

export type Comment = {
  id: string;
  user: User;
  content: string;
  created_at: string;
  score?: number;
  viewer_vote?: "boost" | "fade" | null;
};

export type FeedMessage = {
  type: "new_post" | "new_prediction" | "new_vote" | "position_open" | "position_close" | string;
  post_id?: string;
  user_id?: string;
  outcome?: PredictionOutcome;
  score?: number;
};

export type ExchangeSession = {
  is_open: boolean;
  opens_at_ts: number;
  closes_at_ts: number;
  timezone: string;
  now_label: string;
  enforced: boolean;
};

export type ExchangePosition = {
  id: number;
  symbol: string;
  direction: Direction;
  amount: number;
  entry_price: number;
  exit_price: number | null;
  status: "open" | "closed";
  realized_pnl: number;
  opened_ts: number;
  closed_ts: number | null;
  current_price?: number | null;
  unrealized_pnl?: number | null;
  gross_value?: number | null;
};

export type ExchangeStats = {
  handle: string;
  balance: number;
  open_positions: number;
  closed_positions: number;
  winning_positions: number;
  losing_positions: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_staked: number;
};

export type ExchangeBoard = {
  session: ExchangeSession;
  stats: ExchangeStats;
  positions: ExchangePosition[];
};
