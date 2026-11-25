import type { AsyncState } from "../api/useAsync";
import type { TrackRecord } from "../api/types";
import { formatChange, formatPercent, formatUtc } from "../format";
import { DirectionBadge } from "./DirectionBadge";
import { Card, Empty, ErrorBox, Loading } from "./StateViews";

export function TrackRecordCard({ state, onRetry }: { state: AsyncState<TrackRecord>; onRetry: () => void }) {
  return (
    <Card title="Track record" id="track-title">
      {state.status === "loading" && <Loading label="Checking past forecasts…" />}
      {state.status === "error" && <ErrorBox error={state.error} onRetry={onRetry} />}
      {state.status === "success" && <Record record={state.data} />}
    </Card>
  );
}

function Record({ record }: { record: TrackRecord }) {
  const waiting = record.pending > 0 ? ` ${record.pending} still waiting for the three hours to pass.` : "";
  if (record.checked === 0) return <Empty>No finished forecast to check yet.{waiting}</Empty>;
  return (
    <>
      <p className="price">{record.checked < 30 ? `${record.correct}/${record.checked}` : formatPercent(record.correct / record.checked, 0)}</p>
      <p className="hint">
        {record.correct} of {record.checked} saved forecasts were right.{waiting}
        {record.checked < 30 && " Too few to judge the model yet."}
        {record.not_checkable > 0 && ` ${record.not_checkable} are too old to check.`}
      </p>
      <div className="table-wrap">
        <table>
          <caption className="sr-only">Forecasts compared with what happened</caption>
          <thead>
            <tr>
              <th scope="col">Candle</th>
              <th scope="col">Forecast</th>
              <th scope="col">Happened</th>
              <th scope="col">Move</th>
              <th scope="col">Result</th>
            </tr>
          </thead>
          <tbody>
            {record.items.map((i) => (
              <tr key={i.id}>
                <td>{formatUtc(i.latest_candle_utc)}</td>
                <td><DirectionBadge label={i.label} /></td>
                <td><DirectionBadge label={i.actual} /></td>
                <td>{formatChange(i.return_pct)}</td>
                <td className={i.correct ? "pos" : "neg"}>{i.correct ? "Right" : "Wrong"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
