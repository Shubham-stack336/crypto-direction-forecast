import { useState } from "react";

import { getMarket } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useAppData } from "../appData";
import { CompareChart } from "../components/CompareChart";
import { Card, ErrorBox, Loading } from "../components/StateViews";
import { symbolToSlug } from "../format";

const MAX = 4;
const RANGES = [{ label: "1 day", hours: 24 }, { label: "3 days", hours: 72 }, { label: "7 days", hours: 168 }];

export default function ComparePage() {
  const { coins } = useAppData();
  const [picked, setPicked] = useState(["BTC-USDT", "ETH-USDT", "SOL-USDT"]);
  const [hours, setHours] = useState(72);
  const data = useAsync(
    (signal) => Promise.all(picked.map(async (slug) => ({
      name: slug.split("-")[0], candles: (await getMarket(slug, signal, hours)).candles,
    }))),
    [picked.join(), hours],
  );
  const options = coins.state.status === "success" ? coins.state.data.map((c) => symbolToSlug(c.symbol)) : [];
  const free = options.filter((s) => !picked.includes(s));

  return (
    <>
      <div className="page-head">
        <h1>Compare</h1>
        <p>Put up to four coins on one scale and see which moved more.</p>
      </div>
      <Card title="Price change" id="compare-title">
        <div className="toolbar">
          <div className="chips">
            {picked.map((slug) => (
              <button
                key={slug} type="button" className="chip" disabled={picked.length === 1}
                aria-label={`Remove ${slug.split("-")[0]}`}
                onClick={() => setPicked(picked.filter((s) => s !== slug))}
              >
                {slug.split("-")[0]} ×
              </button>
            ))}
            {picked.length < MAX && free.length > 0 && (
              <select aria-label="Add a coin" value="" onChange={(e) => e.target.value && setPicked([...picked, e.target.value])}>
                <option value="">Add a coin…</option>
                {free.map((s) => <option key={s} value={s}>{s.split("-")[0]}</option>)}
              </select>
            )}
          </div>
          <div className="segmented" role="group" aria-label="Period">
            {RANGES.map((r) => (
              <button key={r.hours} type="button" aria-pressed={hours === r.hours} onClick={() => setHours(r.hours)}>{r.label}</button>
            ))}
          </div>
        </div>
        {data.state.status === "loading" && <Loading label="Loading prices…" />}
        {data.state.status === "error" && <ErrorBox error={data.state.error} onRetry={data.reload} />}
        {data.state.status === "success" && <CompareChart series={data.state.data} />}
      </Card>
    </>
  );
}
