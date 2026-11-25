import { useState } from "react";

import { scanMarket, toApiError, type ApiError } from "../api/client";
import type { ScanRow } from "../api/types";
import { formatChange, formatPercent, formatPrice, symbolToSlug } from "../format";
import { DirectionBadge } from "./DirectionBadge";
import { Card, Empty, ErrorBox, Loading } from "./StateViews";

type State = { status: "idle" } | { status: "loading" } | { status: "error"; error: ApiError } | { status: "done"; rows: ScanRow[] };

export function Scanner({ onSelect }: { onSelect: (slug: string) => void }) {
  const [state, setState] = useState<State>({ status: "idle" });
  const run = async () => {
    setState({ status: "loading" });
    try {
      const { items } = await scanMarket();
      const top = (r: ScanRow) => Math.max(...Object.values(r.probabilities));
      setState({ status: "done", rows: [...items].sort((a, b) => top(b) - top(a)) });
    } catch (error) {
      setState({ status: "error", error: toApiError(error) });
    }
  };

  return (
    <Card title="Market scanner" id="scanner-title">
      <p className="hint">Runs the model on the 12 most traded coins. Scans are not added to the history.</p>
      <button type="button" className="button" onClick={run} disabled={state.status === "loading"}>
        {state.status === "loading" ? "Scanning…" : "Scan 12 coins"}
      </button>
      {state.status === "idle" && <Empty>Run a scan to compare coins side by side.</Empty>}
      {state.status === "loading" && <Loading label="Fetching candles for each coin…" />}
      {state.status === "error" && <ErrorBox error={state.error} onRetry={run} />}
      {state.status === "done" && (
        <ul className="scan-grid">
          {state.rows.map((r) => (
            <li key={r.symbol}>
              <button type="button" className="scan-tile" onClick={() => onSelect(symbolToSlug(r.symbol))}>
                <span className="scan-top">
                  <strong>{r.symbol.split("/")[0]}</strong>
                  <span className={r.change_pct >= 0 ? "pos" : "neg"}>{formatChange(r.change_pct)}</span>
                </span>
                <span className="mono">{formatPrice(r.last)}</span>
                <span className="scan-top">
                  <DirectionBadge label={r.label} />
                  <span className="mono">{formatPercent(r.probabilities[r.label])}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
