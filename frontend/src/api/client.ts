import type { Coin, HistoryPage, MarketData, ModelStatus, PredictionResult, Readiness, RecordSummary, ScanRow, TrackRecord } from "./types";

const DEFAULT_LOCAL_URL = "http://127.0.0.1:8000";
const PRODUCTION_API_URL = "https://crypto-direction-api-6u98.onrender.com";
// A free hosting plan can need about a minute to wake a sleeping server on the first request.
const REQUEST_TIMEOUT_MS = 60_000;

function resolveApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  // If envUrl is the old/broken URL without -6u98, auto-repair to the live deployed instance
  if (envUrl && envUrl.includes("crypto-direction-api.onrender.com") && !envUrl.includes("6u98")) {
    return PRODUCTION_API_URL;
  }
  if (envUrl && envUrl.trim() !== "") {
    return envUrl.trim().replace(/\/+$/, "");
  }
  // When running in production on Vercel, default to the live Render backend
  if (import.meta.env.PROD) {
    return PRODUCTION_API_URL;
  }
  return DEFAULT_LOCAL_URL;
}

export const API_BASE_URL = resolveApiBaseUrl();

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function toApiError(error: unknown): ApiError {
  return error instanceof ApiError ? error : new ApiError(0, "Something unexpected went wrong.");
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, timeoutMs = REQUEST_TIMEOUT_MS } = options;

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  signal?.addEventListener("abort", () => controller.abort(), { once: true });

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(0, timedOut ? "The API took too long to respond." : "Cannot reach the API.");
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let detail = `The API returned an error (${response.status}).`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") detail = payload.detail;
      else if (response.status === 422) detail = "The request was not valid.";
    } catch {
      // keep the generic message
    }
    throw new ApiError(response.status, detail);
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, "The API sent an unreadable response.");
  }
}

export const getLive = (signal?: AbortSignal) => request<{ status: string }>("/health/live", { signal });
export const getReady = (signal?: AbortSignal) => request<Readiness>("/health/ready", { signal });

export const getMarket = (symbol: string, signal?: AbortSignal, hours = 24) =>
  request<MarketData>(`/api/v1/market/${encodeURIComponent(symbol)}?hours=${hours}`, { signal });

export const getRecord = (signal?: AbortSignal) => request<RecordSummary>("/api/v1/predictions", { signal });

export const getCoins = (signal?: AbortSignal) =>
  request<{ items: Coin[] }>("/api/v1/coins", { signal }).then((r) => r.items);

export const scanMarket = (limit = 12) => request<{ items: ScanRow[] }>(`/api/v1/coins/scan?limit=${limit}`);

export const getTrackRecord = (symbol: string, signal?: AbortSignal) =>
  request<TrackRecord>(`/api/v1/predictions/${encodeURIComponent(symbol)}/track-record`, { signal });

export const getModelStatus = (symbol: string, signal?: AbortSignal) =>
  request<ModelStatus>(`/api/v1/models/${encodeURIComponent(symbol)}/status`, { signal });

export const createPrediction = (symbol: string, signal?: AbortSignal) =>
  request<PredictionResult>(`/api/v1/predictions/${encodeURIComponent(symbol)}`, {
    method: "POST",
    body: { timeframe: "1h" },
    signal,
  });

export const getHistory = (symbol: string, limit = 20, offset = 0, signal?: AbortSignal) =>
  request<HistoryPage>(
    `/api/v1/predictions/${encodeURIComponent(symbol)}/history?limit=${limit}&offset=${offset}`,
    { signal },
  );
