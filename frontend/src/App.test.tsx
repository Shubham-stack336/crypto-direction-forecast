import { fireEvent, render, screen, within } from "@testing-library/react";
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
    "GET /api/v1/market/SHIB-USDT": () => ({ body: { ...market, symbol: "SHIB/USDT" } }),
    "POST /api/v1/predictions/BTC-USDT": () => {
      saved.push(savedItem);
      return { body: prediction };
    },
    "GET /api/v1/predictions/BTC-USDT/track-record": () => ({
      body: {
        symbol: "BTC/USDT", checked: 2, correct: 1, pending: 1, not_checkable: 0,
        items: [
          { id: 9, latest_candle_utc: "2026-01-20T01:00:00+00:00", label: "UP", actual: "DOWN", return_pct: -0.8, correct: false },
        ],
      },
    }),
    "GET /api/v1/coins": () => ({
      body: {
        items: [
          { symbol: "BTC/USDT", last: 81234.5, change_pct: 1.2, quote_volume: 9e9, model: "dedicated" },
          { symbol: "SHIB/USDT", last: 0.00001234, change_pct: -3.4, quote_volume: 1e7, model: "universal" },
        ],
      },
    }),
    "GET /api/v1/coins/scan": () => ({
      body: {
        disclaimer: "x",
        items: [
          { symbol: "SHIB/USDT", last: 0.00001234, change_pct: -3.4, label: "DOWN", probabilities: { UP: 0.2, DOWN: 0.5, SIDEWAYS: 0.3 }, model: "universal" },
        ],
      },
    }),
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

const region = (name: string) => screen.findByRole("region", { name });

function open(path: string) {
  window.history.pushState({}, "", path);
  return render(<App />);
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  localStorage.clear();
});

describe("App", () => {
  it("always shows the uncertainty disclaimer", async () => {
    installApi();
    open("/forecast");
    expect(screen.getByRole("note", { name: /uncertainty disclaimer/i })).toHaveTextContent(/not financial advice/i);
    await screen.findByText(/API ready/);
  });

  it("shows API status, market freshness and an empty history", async () => {
    installApi();
    open("/forecast");

    expect(screen.getAllByRole("status").some((el) => /Checking API/.test(el.textContent ?? ""))).toBe(true);
    expect(screen.getByText(/can take up to a minute to wake up/)).toBeInTheDocument();
    expect(await screen.findByText("API ready · database connected")).toBeInTheDocument();

    const marketCard = await region("Market data");
    expect(await within(marketCard).findByLabelText("81,234.5")).toBeInTheDocument();
    expect(within(marketCard).getByText(/Data is fresh/)).toBeInTheDocument();

    expect(await within(await region("Prediction history")).findByText(/No forecasts saved yet/)).toBeInTheDocument();
    expect(screen.getByText(/3 candles \(3 hours ahead\)/)).toBeInTheDocument();
  });

  it("shows evaluation metrics on the model page", async () => {
    installApi();
    open("/model");
    const modelCard = await region("Model evaluation");
    expect(await within(modelCard).findByText("Random forest (the model used)")).toBeInTheDocument();
    expect(within(modelCard).getByText("Naive: always the most common class")).toBeInTheDocument();
    expect(within(modelCard).getByText("n/a")).toBeInTheDocument();

  });

  it("home shows the price, coin cards and links to the forecast", async () => {
    const user = userEvent.setup();
    installApi();
    open("/");
    expect(await screen.findByLabelText("81,234.5")).toBeInTheDocument();
    const cards = await screen.findByRole("region", { name: "Most traded coins" });
    expect(await within(cards).findByText("Shiba Inu")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Forecast BTC" }));
    expect(await screen.findByRole("button", { name: /Get forecast for BTC\/USDT/ })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/forecast/BTC-USDT");
  });

  it("night mode can be switched on and is remembered", async () => {
    const user = userEvent.setup();
    installApi();
    open("/about");
    await user.click(screen.getByRole("button", { name: /Theme: Match device/ }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("theme")).toBe("dark");
    await user.click(screen.getByRole("button", { name: /Theme: Night/ }));
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("says how reliable a weak forecast has been", async () => {
    const user = userEvent.setup();
    installApi({
      "POST /api/v1/predictions/BTC-USDT": () => ({
        body: { ...prediction, confidence: { level: "weak", historical_accuracy: 0.37, historical_rows: 633 } },
      }),
    });
    open("/forecast");
    await user.click(await screen.findByRole("button", { name: /Get forecast/ }));
    expect(await screen.findByText(/right 37% of the time on 633 past cases.*no signal/)).toBeInTheDocument();
  });

  it("price alerts are validated, fire when reached, and can be removed", async () => {
    const user = userEvent.setup();
    installApi();
    localStorage.setItem("price-alerts", JSON.stringify([
      { id: "a", slug: "BTC-USDT", side: "above", price: 80000, firedAt: null }, { broken: true },
    ]));
    open("/alerts");
    expect(await screen.findByText(/Reached/)).toBeInTheDocument();
    await user.type(await screen.findByLabelText("Price (USDT)"), "100");
    await user.click(screen.getByRole("button", { name: "Add alert" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/already above 100/);
    await user.clear(screen.getByLabelText("Price (USDT)"));
    await user.type(screen.getByLabelText("Price (USDT)"), "99999");
    await user.click(screen.getByRole("button", { name: "Add alert" }));
    expect(screen.getByText("Waiting")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Remove alert for BTC" })[0]);
    expect(screen.queryByText("Waiting")).toBeNull();
  });

  it("the record page compares with a constant guess", async () => {
    installApi({
      "GET /api/v1/predictions": () => ({
        body: { checked: 40, correct: 18, open: 2, baseline_correct: 16, by_symbol: [{ name: "BTC/USDT", checked: 40, correct: 18 }], by_model: [], by_label: [] },
      }),
    });
    open("/record");
    expect(await within(await region("Overall")).findByText("45.0%")).toBeInTheDocument();
    expect(screen.getByText(/would have scored 40.0%/)).toBeInTheDocument();
  });

  it("compares coins", async () => {
    const user = userEvent.setup();
    const candle = (close: number, i: number) => ({ timestamp: `t${i}`, open: close, high: close, low: close, close, volume: 1 });
    const body = { ...market, candles: [100, 105, 110].map(candle) };
    installApi({
      "GET /api/v1/market/BTC-USDT": () => ({ body }), "GET /api/v1/market/ETH-USDT": () => ({ body }), "GET /api/v1/market/SOL-USDT": () => ({ body }),
    });
    open("/compare");
    expect(await screen.findAllByText(/\+10\.00%/)).not.toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Remove SOL" }));
    expect(screen.queryByRole("button", { name: "Remove SOL" })).toBeNull();
  });

  it("links to the author's LinkedIn and GitHub", async () => {
    installApi();
    open("/about");
    await screen.findByRole("heading", { name: "About" });
    for (const link of screen.getAllByRole("link", { name: "LinkedIn" }))
      expect(link).toHaveAttribute("href", "https://www.linkedin.com/in/shubham-kumar-30877a398/");
    for (const link of screen.getAllByRole("link", { name: "GitHub" }))
      expect(link).toHaveAttribute("href", "https://github.com/Shubham-stack336");
  });

  it("shows a not found page for unknown addresses", async () => {
    installApi();
    open("/nothing-here");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });

  it("a slide that is let go too early does not run a forecast", async () => {
    const fetchMock = installApi();
    open("/forecast");
    const button = await screen.findByRole("button", { name: /Get forecast/ });
    button.getBoundingClientRect = () => ({ width: 400, height: 76 }) as DOMRect;
    fireEvent.pointerDown(button, { clientX: 10 });
    fireEvent.pointerMove(button, { clientX: 60 });
    fireEvent.pointerUp(button, { clientX: 60 });
    fireEvent.click(button);
    const posted = () => fetchMock.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "POST");
    expect(posted()).toBe(false);
    fireEvent.pointerDown(button, { clientX: 10 });
    fireEvent.pointerMove(button, { clientX: 330 });
    fireEvent.pointerUp(button, { clientX: 330 });
    fireEvent.click(button);
    await screen.findByText(/Next 3 hours/);
    expect(posted()).toBe(true);
  });

  it("runs a forecast on click, shows probabilities, and refreshes the history", async () => {
    const user = userEvent.setup();
    installApi();
    open("/forecast");
    await within(await region("Prediction history")).findByText(/No forecasts saved yet/);

    await user.click(screen.getByRole("button", { name: /Get forecast for BTC\/USDT/ }));

    const card = await region("Direction forecast");
    expect(await within(card).findByText(/Next 3 hours/)).toBeInTheDocument();
    const bars = within(card).getByRole("list", { name: "Probability estimates" });
    expect(bars).toHaveTextContent("48.1%");
    expect(bars).toHaveTextContent("27.3%");
    expect(bars).toHaveTextContent("24.6%");
    expect(within(card).getByText(/not guarantees/i)).toBeInTheDocument();

    const historyCard = await region("Prediction history");
    expect(await within(historyCard).findByText(/Showing the latest 1 of 1/)).toBeInTheDocument();
  });

  it("searches coins, keeps a watchlist and opens a coin", async () => {
    localStorage.clear();
    const user = userEvent.setup();
    installApi();
    open("/coins");
    const explorer = await region("Coin explorer");
    await user.type(await within(explorer).findByLabelText("Search coins"), "shi");
    expect(within(explorer).getByText("0.00001234")).toBeInTheDocument();
    expect(within(explorer).queryByLabelText("Open BTC")).toBeNull();
    await user.click(within(explorer).getByRole("button", { name: "Watch SHIB" }));
    expect(JSON.parse(localStorage.getItem("watchlist")!)).toEqual(["SHIB-USDT"]);
    await user.click(within(explorer).getByRole("button", { name: "Open SHIB" }));
    expect(await screen.findByRole("button", { name: /Get forecast for SHIB\/USDT/ })).toBeInTheDocument();
  });

  it("scans only on request and shows the track record", async () => {
    const user = userEvent.setup();
    const fetchMock = installApi();
    open("/forecast");
    expect(await within(await region("Track record")).findByText(/1 of 2 saved forecasts were right/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/scan"))).toBe(false);
    await user.click(within(screen.getByRole("navigation")).getByRole("link", { name: "Scanner" }));
    await user.click(await screen.findByRole("button", { name: "Scan 12 coins" }));
    expect(await within(await region("Market scanner")).findByText("50.0%")).toBeInTheDocument();
  });

  it("does not run a forecast until the user asks for one", async () => {
    const fetchMock = installApi();
    open("/forecast");
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
    open("/forecast");

    await user.click(await screen.findByRole("button", { name: /Get forecast/ }));

    const card = await region("Direction forecast");
    expect(await within(card).findByRole("alert")).toHaveTextContent(/too old/);
    expect(within(card).getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("keeps the other cards working when market data fails", async () => {
    installApi({
      "GET /api/v1/market/BTC-USDT": () => ({ status: 503, body: { detail: "Market data provider is currently unavailable" } }),
    });
    open("/forecast");

    expect(await within(await region("Market data")).findByRole("alert")).toHaveTextContent(/currently unavailable/);
    expect(await within(await region("Track record")).findByText(/1 of 2/)).toBeInTheDocument();
  });

  it("shows an offline state when the API cannot be reached", async () => {
    installApi({
      "GET /health/live": () => new TypeError("Failed to fetch"),
      "GET /health/ready": () => new TypeError("Failed to fetch"),
      "GET /api/v1/market/BTC-USDT": () => new TypeError("Failed to fetch"),
      "GET /api/v1/models/BTC-USDT/status": () => new TypeError("Failed to fetch"),
      "GET /api/v1/predictions/BTC-USDT/history": () => new TypeError("Failed to fetch"),
    });
    open("/forecast");

    expect(await screen.findByText("API offline")).toBeInTheDocument();
    expect(await within(await region("Market data")).findByRole("alert")).toHaveTextContent("Cannot reach the API.");
  });

  it("explains when the API is up but not ready", async () => {
    installApi({
      "GET /health/ready": () => ({ status: 503, body: { detail: "Database is unavailable" } }),
    });
    open("/forecast");
    expect(await screen.findByText(/API online, not ready: Database is unavailable/)).toBeInTheDocument();
  });

  it("tells the user when history storage is switched off", async () => {
    installApi({
      "GET /api/v1/predictions/BTC-USDT/history": () => ({
        status: 503,
        body: { detail: "Prediction history storage is not configured" },
      }),
    });
    open("/forecast");
    expect(await within(await region("Prediction history")).findByRole("alert")).toHaveTextContent(/not configured/);
  });
});
