import { useNavigate, useParams } from "react-router";

import { getModelStatus } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useAppData } from "../appData";
import { ModelCard } from "../components/ModelCard";
import { slugToSymbol, symbolsFromModels } from "../format";

export default function ModelPage() {
  const navigate = useNavigate();
  const { ready } = useAppData();
  const slug = (useParams().slug ?? "BTC-USDT").toUpperCase();
  const model = useAsync((signal) => getModelStatus(slug, signal), [slug]);
  const own = ready.state.status === "success" ? symbolsFromModels(ready.state.data.models) : [];
  return (
    <>
      <div className="page-head">
        <h1>Model</h1>
        <p>How well each model did on data it never saw, next to simple baselines.</p>
      </div>
      <div className="controls">
        <label>
          Model for
          <select value={slug} onChange={(e) => navigate(`/model/${e.target.value}`)}>
            {Array.from(new Set([slug, ...own])).map((s) => <option key={s} value={s}>{slugToSymbol(s)}</option>)}
          </select>
        </label>
      </div>
      <ModelCard state={model.state} onRetry={model.reload} />
    </>
  );
}
