import type { ApiError } from "../api/client";
import type { AsyncState } from "../api/useAsync";
import type { Candle, MarketData } from "../api/types";
import { formatAge, formatUtc } from "../format";
import { BigNumber } from "./BigNumber";
import { Card, ErrorBox, Loading } from "./StateViews";
import { SpatialChart } from "./SpatialChart";

/** Average size of the 3 hour moves in the candles on screen: how calm or wild the coin is now. */
function typicalMove(candles: Candle[]): string {
  const moves = candles.slice(3).map((c, i) => Math.abs(c.close / candles[i].close - 1));
  return moves.length === 0 ? "n/a" : `±${((moves.reduce((a, b) => a + b, 0) / moves.length) * 100).toFixed(2)}%`;
}

interface Props {
  state: AsyncState<MarketData>;
  onRetry: () => void;
  hours: number;
  onHours: (hours: number) => void;
}

export function MarketCard({ state, onRetry, hours, onHours }: Props) {
  return (
    <Card title="Market data" id="market-title">
      {state.status === "loading" && <Loading label="Loading market data…" />}
      {state.status === "error" && <ErrorBox error={state.error as ApiError} onRetry={onRetry} />}
      {state.status === "success" && (
        <>
          <div className="market-price-row">
            <div>
              <BigNumber value={state.data.last_close} />
              <p className="hint">last closed {state.data.timeframe} candle</p>
            </div>
            <p className={state.data.is_fresh ? "fresh fresh-yes" : "fresh fresh-no"}>
              {state.data.is_fresh ? "● Data is fresh" : "● Data is stale"} · {formatAge(state.data.data_age_minutes)} old
            </p>
          </div>

          <div className="segmented" role="group" aria-label="Chart period">
            {[24, 72, 168].map((h) => (
              <button key={h} type="button" aria-pressed={hours === h} onClick={() => onHours(h)}>{h / 24}d</button>
            ))}
          </div>
          <SpatialChart candles={state.data.candles} />

          <dl className="facts">
            <dt>Candle started at</dt>
            <dd>{formatUtc(state.data.latest_closed_candle_utc)}</dd>
            <dt>Typical 3 hour move</dt>
            <dd>{typicalMove(state.data.candles)}</dd>
            <dt>Candles loaded</dt>
            <dd>{state.data.candles.length} most recent</dd>
          </dl>
        </>
      )}
    </Card>
  );
}
