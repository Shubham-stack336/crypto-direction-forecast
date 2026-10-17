import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createPrediction, getHistory, getMarket } from "./client";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("api client", () => {
  it("returns parsed JSON and builds the URL from the symbol", async () => {
    const fetchMock = vi.fn(async (_url: unknown) => jsonResponse({ symbol: "BTC/USDT" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getMarket("BTC-USDT");

    expect(result).toEqual({ symbol: "BTC/USDT" });
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/v1\/market\/BTC-USDT$/);
  });

  it("sends a JSON body for predictions", async () => {
    const fetchMock = vi.fn(async (_url: unknown, _init?: RequestInit) => jsonResponse({ label: "UP" }));
    vi.stubGlobal("fetch", fetchMock);

    await createPrediction("BTC-USDT");

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ timeframe: "1h" }));
  });

  it("puts pagination in the query string", async () => {
    const fetchMock = vi.fn(async (_url: unknown) => jsonResponse({ items: [], total: 0, limit: 5, offset: 10 }));
    vi.stubGlobal("fetch", fetchMock);

    await getHistory("BTC-USDT", 5, 10);

    expect(String(fetchMock.mock.calls[0][0])).toContain("/history?limit=5&offset=10");
  });

  it("turns an API error body into a readable ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "Market data is too old" }, 503)));

    await expect(getMarket("BTC-USDT")).rejects.toMatchObject({
      name: "ApiError",
      status: 503,
      message: "Market data is too old",
    });
  });

  it("uses a generic message for validation errors and non-JSON failures", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: [{ msg: "bad" }] }, 422)));
    await expect(getMarket("BTC-USDT")).rejects.toMatchObject({ status: 422, message: "The request was not valid." });

    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>oops</html>", { status: 502 })));
    await expect(getMarket("BTC-USDT")).rejects.toMatchObject({ status: 502 });
  });

  it("reports an unreachable API as status 0", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));

    const error = await getMarket("BTC-USDT").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0, message: "Cannot reach the API." });
  });

  it("gives up on a request that never answers", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: unknown, init?: RequestInit) =>
          new Promise((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
          }),
      ),
    );

    const pending = getMarket("BTC-USDT").catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(61_000);

    expect(await pending).toMatchObject({ status: 0, message: "The API took too long to respond." });
  });

  it("rethrows the abort when the caller cancels", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: unknown, init?: RequestInit) =>
          new Promise((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
          }),
      ),
    );
    const controller = new AbortController();

    const pending = getMarket("BTC-USDT", controller.signal).catch((e: unknown) => e);
    controller.abort();

    expect(await pending).toMatchObject({ name: "AbortError" });
  });
});
