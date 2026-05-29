export type Direction = "long" | "short";
export type PredictionOutcome = "tp_hit" | "sl_hit";

export type User = {
  id: string;
  username: string;
  gold: number;
  total_predictions: number;
  correct_predictions: number;
  trust_level: number;
  created_at: string;
};

export type TradePost = {
  id: string;
  user: User;
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
};

export type FeedMessage = {
  type: "new_post" | "new_prediction" | string;
  post_id?: string;
  user_id?: string;
  outcome?: PredictionOutcome;
};
