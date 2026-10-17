import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { HistoryItem, HistoryPage, MarketData, ModelStatus, PredictionResult } from "./api/types";

// All data below is made up for UI tests only.
const market: MarketData = {
  symbol: "BTC/USDT",
  timeframe: "1h",
  latest_closed_candle_utc: "2026-01-20T11:00:00+00:00",
  last_close: 81234.5,
  data_age_minutes: 12,
  is_fresh: true,
  candles: [],
};

const model: ModelStatus = {
  symbol: "BTC/USDT",
  timeframe: "1h",
  model_version: "v1-2026-01-01",
  feature_version: "v1",
  feature_columns: ["ret_1"],
  classes: ["DOWN", "SIDEWAYS", "UP"],
  horizon_candles: 3,
  threshold: 0.003,
  trained_at_utc: "2026-01-01T00:00:00+00:00",
  train_period: ["a", "b"],
  disclaimer: "x",
  evaluation: {
    candidate_model: "random_forest",
    test_period: ["2026-01-01T00:00:00+00:00", "2026-01-10T00:00:00+00:00"],
    test_rows: 2613,
    test_class_distribution: { SIDEWAYS: 1421, UP: 628, DOWN: 564 },
    results: {
      random_forest: { accuracy: 0.5, balanced_accuracy: 0.4, macro_f1: 0.39, directional_hit_rate: 0.55 },
      naive_most_frequent: { accuracy: 0.54, balanced_accuracy: 0.333, macro_f1: 0.23, directional_hit_rate: null },
    },
  },
};

const prediction: PredictionResult = {
  label: "SIDEWAYS",
  probabilities: { UP: 0.2732, DOWN: 0.2456, SIDEWAYS: 0.4812 },
  symbol: "BTC/USDT",
  timeframe: "1h",
  horizon_candles: 3,
  prediction_time_utc: "2026-01-20T12:00:00+00:00",
  latest_candle_utc: "2026-01-20T11:00:00+00:00",
  model_version: "v1-2026-01-01",
  feature_version: "v1",
  status: "ok",
  data_quality: { rows_used: 499, dropped_incomplete_candle: true, data_age_minutes: 12 },
  disclaimer: "x",
  saved: true,
};

const savedItem: HistoryItem = {
  id: 1,
  symbol: "BTC/USDT",
  timeframe: "1h",
  horizon_candles: 3,
  label: "SIDEWAYS",
  probabilities: prediction.probabilities,
  prediction_time_utc: "2026-01-20T12:00:00+00:00",
  latest_candle_utc: "2026-01-20T11:00:00+00:00",
  model_version: "v1-2026-01-01",
  feature_version: "v1",
};

type Reply = { status?: number; body: unknown } | Error;
type Routes = Record<string, (init?: RequestInit) => Reply>;

function installApi(overrides: Routes = {}) {
  const saved: HistoryItem[] = [];
  const routes: Routes = {
    "GET /health/live": () => ({ body: { status: "ok" } }),
    "GET /health/ready": () => ({ body: { status: "ready", models: ["BTC/USDT 1h"], database: "ok" } }),
    "GET /api/v1/market/BTC-USDT": () => ({ body: market }),
    "GET /api/v1/models/BTC-USDT/status": () => ({ body: model }),
    "GET /api/v1/predictions/BTC-USDT/history": () => ({
      body: { items: [...saved].reverse(), total: saved.length, limit: 20, offset: 0 } satisfies HistoryPage,
    }),
    "POST /api/v1/predictions/BTC-USDT": () => {
      saved.push(savedItem);
      return { body: prediction };
    },
    ...overrides,
  };

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${new URL(String(input)).pathname}`;
    const handler = routes[key];
    if (!handler) throw new Error(`Unexpected request: ${key}`);
    const reply = handler(init);
    if (reply instanceof Error) throw reply;
    return new Response(JSON.stringify(reply.body), {
      status: reply.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const region = (name: string) => screen.getByRole("region", { name });

afterEach(() => vi.unstubAllGlobals());

describe("App", () => {
  it("always shows the uncertainty disclaimer", async () => {
    installApi();
    render(<App />);
    expect(screen.getByRole("note", { name: /uncertainty disclaimer/i })).toHaveTextContent(/not financial advice/i);
    await screen.findByText(/API ready/);
  });

  it("shows API status, market freshness, evaluation metrics and an empty history", async () => {
    installApi();
    render(<App />);

    expect(screen.getAllByRole("status").some((el) => /Checking API/.test(el.textContent ?? ""))).toBe(true);
    expect(screen.getByText(/can take up to a minute to wake up/)).toBeInTheDocument();
    expect(await screen.findByText("API ready · database connected")).toBeInTheDocument();

    const marketCard = region("Market data");
    expect(await within(marketCard).findByText("81,234.5")).toBeInTheDocument();
    expect(within(marketCard).getByText(/Data is fresh/)).toBeInTheDocument();

    const modelCard = region("Model evaluation");
    expect(await within(modelCard).findByText("Random forest (the model used)")).toBeInTheDocument();
    expect(within(modelCard).getByText("Naive: always the most common class")).toBeInTheDocument();
    expect(within(modelCard).getByText("n/a")).toBeInTheDocument();

    expect(await within(region("Prediction history")).findByText(/No forecasts saved yet/)).toBeInTheDocument();
    expect(screen.getByText(/3 candles \(3 hours ahead\)/)).toBeInTheDocument();
  });

  it("runs a forecast on click, shows probabilities, and refreshes the history", async () => {
    const user = userEvent.setup();
    installApi();
    render(<App />);
    await within(region("Prediction history")).findByText(/No forecasts saved yet/);

    await user.click(screen.getByRole("button", { name: /Get forecast for BTC\/USDT/ }));

    const card = region("Direction forecast");
    expect(await within(card).findByText(/Next 3 hours/)).toBeInTheDocument();
    const bars = within(card).getByRole("list", { name: "Probability estimates" });
    expect(bars).toHaveTextContent("48.1%");
    expect(bars).toHaveTextContent("27.3%");
    expect(bars).toHaveTextContent("24.6%");
    expect(within(card).getByText(/not guarantees/i)).toBeInTheDocument();

    const historyCard = region("Prediction history");
    expect(await within(historyCard).findByText(/Showing the latest 1 of 1/)).toBeInTheDocument();
  });

  it("does not run a forecast until the user asks for one", async () => {
    const fetchMock = installApi();
    render(<App />);
    await screen.findByText("API ready · database connected");
    expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "POST")).toBe(false);
  });

  it("shows the API's message when a forecast fails, and a retry button", async () => {
    const user = userEvent.setup();
    installApi({
      "POST /api/v1/predictions/BTC-USDT": () => ({
        status: 503,
        body: { detail: "Market data is too old to produce a reliable prediction" },
      }),
    });
    render(<App />);

    await user.click(screen.getByRole("button", { name: /Get forecast/ }));

    const card = region("Direction forecast");
    expect(await within(card).findByRole("alert")).toHaveTextContent(/too old/);
    expect(within(card).getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("keeps the other cards working when market data fails", async () => {
    installApi({
      "GET /api/v1/market/BTC-USDT": () => ({ status: 503, body: { detail: "Market data provider is currently unavailable" } }),
    });
    render(<App />);

    expect(await within(region("Market data")).findByRole("alert")).toHaveTextContent(/currently unavailable/);
    expect(await within(region("Model evaluation")).findByText("Random forest (the model used)")).toBeInTheDocument();
  });

  it("shows an offline state when the API cannot be reached", async () => {
    installApi({
      "GET /health/live": () => new TypeError("Failed to fetch"),
      "GET /health/ready": () => new TypeError("Failed to fetch"),
      "GET /api/v1/market/BTC-USDT": () => new TypeError("Failed to fetch"),
      "GET /api/v1/models/BTC-USDT/status": () => new TypeError("Failed to fetch"),
      "GET /api/v1/predictions/BTC-USDT/history": () => new TypeError("Failed to fetch"),
    });
    render(<App />);

    expect(await screen.findByText("API offline")).toBeInTheDocument();
    expect(await within(region("Market data")).findByRole("alert")).toHaveTextContent("Cannot reach the API.");
  });

  it("explains when the API is up but not ready", async () => {
    installApi({
      "GET /health/ready": () => ({ status: 503, body: { detail: "Database is unavailable" } }),
    });
    render(<App />);
    expect(await screen.findByText(/API online, not ready: Database is unavailable/)).toBeInTheDocument();
  });

  it("tells the user when history storage is switched off", async () => {
    installApi({
      "GET /api/v1/predictions/BTC-USDT/history": () => ({
        status: 503,
        body: { detail: "Prediction history storage is not configured" },
      }),
    });
    render(<App />);
    expect(await within(region("Prediction history")).findByRole("alert")).toHaveTextContent(/not configured/);
  });
});
