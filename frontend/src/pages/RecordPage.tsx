import { getRecord } from "../api/client";
import type { RecordSummary, Tally } from "../api/types";
import { useAsync } from "../api/useAsync";
import { Card, Empty, ErrorBox, Loading } from "../components/StateViews";
import { formatPercent } from "../format";

const ENOUGH = 30;

export default function RecordPage() {
  const record = useAsync((signal) => getRecord(signal), []);
  return (
    <>
      <div className="page-head">
        <h1>Record</h1>
        <p>Every finished forecast of every coin, right or wrong, next to the best constant guess.</p>
      </div>
      {record.state.status === "loading" && <Loading label="Loading the record…" />}
      {record.state.status === "error" && <ErrorBox error={record.state.error} onRetry={record.reload} />}
      {record.state.status === "success" && <Summary data={record.state.data} />}
    </>
  );
}

const rate = (correct: number, checked: number) =>
  checked < ENOUGH ? `${correct}/${checked}` : formatPercent(correct / checked);

function Summary({ data }: { data: RecordSummary }) {
  if (data.checked === 0)
    return <Card title="Overall" id="overall-title"><Empty>No finished forecast yet. {data.open} still open.</Empty></Card>;
  return (
    <div className="grid">
      <Card title="Overall" id="overall-title">
        <p className="price">{rate(data.correct, data.checked)}</p>
        <p className="hint">
          Always saying the most common outcome would have scored {rate(data.baseline_correct, data.checked)}. {data.open} forecasts are still open.
          {data.checked < ENOUGH && " Too few to judge yet."}
        </p>
      </Card>
      <TallyCard title="By forecast" id="by-label-title" rows={data.by_label} />
      <TallyCard title="By coin" id="by-coin-title" rows={data.by_symbol} />
      <TallyCard title="By model" id="by-model-title" rows={data.by_model} note="Models named shadow are being tested on live data and never answer users." />
    </div>
  );
}

function TallyCard({ title, id, rows, note }: { title: string; id: string; rows: Tally[]; note?: string }) {
  return (
    <Card title={title} id={id}>
      {note && <p className="hint">{note}</p>}
      <ul className="rows">
        {rows.map((r) => (
          <li key={r.name}><span>{r.name}</span><span className="mono">{rate(r.correct, r.checked)} {r.checked >= ENOUGH && <small>of {r.checked}</small>}</span></li>
        ))}
      </ul>
    </Card>
  );
}
