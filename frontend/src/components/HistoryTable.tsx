import type { AsyncState } from "../api/useAsync";
import type { HistoryPage } from "../api/types";
import { formatPercent, formatUtc } from "../format";
import { DirectionBadge } from "./DirectionBadge";
import { Card, Empty, ErrorBox, Loading } from "./StateViews";

interface Props {
  state: AsyncState<HistoryPage>;
  onRetry: () => void;
}

export function HistoryTable({ state, onRetry }: Props) {
  return (
    <Card title="Prediction history" id="history-title">
      {state.status === "loading" && <Loading label="Loading history…" />}
      {state.status === "error" && <ErrorBox error={state.error} onRetry={onRetry} />}
      {state.status === "success" && state.data.items.length === 0 && (
        <Empty>No forecasts saved yet. Get a forecast and it will appear here.</Empty>
      )}
      {state.status === "success" && state.data.items.length > 0 && (
        <>
          <p className="hint">
            Showing the latest {state.data.items.length} of {state.data.total}.
          </p>
          <div className="table-wrap">
            <table>
              <caption className="sr-only">Saved forecasts, newest first</caption>
              <thead>
                <tr>
                  <th scope="col">Made at</th>
                  <th scope="col">Forecast</th>
                  <th scope="col">UP</th>
                  <th scope="col">SIDEWAYS</th>
                  <th scope="col">DOWN</th>
                  <th scope="col">Model</th>
                </tr>
              </thead>
              <tbody>
                {state.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>{formatUtc(item.prediction_time_utc)}</td>
                    <td>
                      <DirectionBadge label={item.label} />
                    </td>
                    <td>{formatPercent(item.probabilities.UP)}</td>
                    <td>{formatPercent(item.probabilities.SIDEWAYS)}</td>
                    <td>{formatPercent(item.probabilities.DOWN)}</td>
                    <td>{item.model_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
