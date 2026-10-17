import type { ApiError } from "../api/client";
import type { AsyncState } from "../api/useAsync";
import type { MarketData } from "../api/types";
import { formatAge, formatPrice, formatUtc } from "../format";
import { Card, ErrorBox, Loading } from "./StateViews";

interface Props {
  state: AsyncState<MarketData>;
  onRetry: () => void;
}

export function MarketCard({ state, onRetry }: Props) {
  return (
    <Card title="Market data" id="market-title">
      {state.status === "loading" && <Loading label="Loading market data…" />}
      {state.status === "error" && <ErrorBox error={state.error as ApiError} onRetry={onRetry} />}
      {state.status === "success" && (
        <>
          <p className="price">{formatPrice(state.data.last_close)}</p>
          <p className="hint">last closed {state.data.timeframe} candle</p>
          <p className={state.data.is_fresh ? "fresh fresh-yes" : "fresh fresh-no"}>
            {state.data.is_fresh ? "● Data is fresh" : "● Data is stale"} · {formatAge(state.data.data_age_minutes)} old
          </p>
          <dl className="facts">
            <dt>Candle closed at</dt>
            <dd>{formatUtc(state.data.latest_closed_candle_utc)}</dd>
            <dt>Candles loaded</dt>
            <dd>{state.data.candles.length} most recent</dd>
          </dl>
        </>
      )}
    </Card>
  );
}
