export type Direction = "UP" | "DOWN" | "SIDEWAYS";

export interface Readiness {
  status: string;
  models: string[];
  database: string;
}

export interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MarketData {
  symbol: string;
  timeframe: string;
  latest_closed_candle_utc: string;
  last_close: number;
  data_age_minutes: number;
  is_fresh: boolean;
  candles: Candle[];
}

export interface Confidence {
  level: "clear" | "weak";
  historical_accuracy: number | null;
  historical_rows: number;
}

export interface Tally {
  name: string;
  checked: number;
  correct: number;
}

export interface RecordSummary {
  checked: number;
  correct: number;
  open: number;
  baseline_correct: number;
  by_symbol: Tally[];
  by_model: Tally[];
  by_label: Tally[];
}

export interface PredictionResult {
  label: Direction;
  probabilities: Record<Direction, number>;
  symbol: string;
  timeframe: string;
  horizon_candles: number;
  prediction_time_utc: string;
  latest_candle_utc: string;
  model_version: string;
  feature_version: string;
  status: string;
  data_quality: {
    rows_used: number;
    dropped_incomplete_candle: boolean;
    data_age_minutes: number;
  };
  disclaimer: string;
  saved: boolean;
  confidence?: Confidence | null;
}

export interface HistoryItem {
  id: number;
  symbol: string;
  timeframe: string;
  horizon_candles: number;
  label: Direction;
  probabilities: Record<Direction, number>;
  prediction_time_utc: string;
  latest_candle_utc: string;
  model_version: string;
  feature_version: string;
}

export interface HistoryPage {
  items: HistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface Coin {
  symbol: string;
  last: number;
  change_pct: number;
  quote_volume: number;
  model: "dedicated" | "universal";
}

export interface ScanRow {
  confidence?: Confidence | null;
  symbol: string;
  last: number;
  change_pct: number;
  label: Direction;
  probabilities: Record<Direction, number>;
  model: "dedicated" | "universal";
}

export interface TrackRecord {
  symbol: string;
  checked: number;
  correct: number;
  pending: number;
  not_checkable: number;
  items: { id: number; latest_candle_utc: string; label: Direction; actual: Direction; return_pct: number; correct: boolean }[];
}

export interface ModelMetrics {
  accuracy: number;
  balanced_accuracy: number;
  macro_f1: number;
  directional_hit_rate: number | null;
}

export interface Evaluation {
  candidate_model: string;
  test_period: [string, string];
  test_rows: number;
  test_class_distribution: Record<string, number>;
  results: Record<string, ModelMetrics>;
  note?: string;
}

export interface ModelStatus {
  symbol: string;
  timeframe: string;
  model_version: string;
  feature_version: string;
  feature_columns: string[];
  classes: string[];
  horizon_candles: number;
  threshold: number;
  trained_at_utc: string;
  train_period: string[];
  evaluation: Evaluation | null;
  model_kind?: "dedicated" | "universal";
  disclaimer: string;
}
