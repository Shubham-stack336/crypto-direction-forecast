import { useCallback, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { createPrediction, getHistory, getMarket, getModelStatus, getTrackRecord, toApiError } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useAppData } from "../appData";
import { Controls } from "../components/Controls";
import { HistoryTable } from "../components/HistoryTable";
import { MarketCard } from "../components/MarketCard";
import { PredictionCard, type PredictionState } from "../components/PredictionCard";
import { TrackRecordCard } from "../components/TrackRecordCard";
import { coinName } from "../coinNames";
import { slugToSymbol, symbolToSlug } from "../format";

export default function ForecastPage() {
  const slug = (useParams().slug ?? "BTC-USDT").toUpperCase();
  return <Forecast key={slug} slug={slug} />;
}

function Forecast({ slug }: { slug: string }) {
  const navigate = useNavigate();
  const { coins, watchlist, toggleWatch } = useAppData();
  const market = useAsync((signal) => getMarket(slug, signal), [slug]);
  const model = useAsync((signal) => getModelStatus(slug, signal), [slug]);
  const history = useAsync((signal) => getHistory(slug, 20, 0, signal), [slug]);
  const track = useAsync((signal) => getTrackRecord(slug, signal), [slug]);
  const [prediction, setPrediction] = useState<PredictionState>({ status: "idle" });
  const latestRequest = useRef(0);

  const run = useCallback(async () => {
    const id = ++latestRequest.current;
    setPrediction({ status: "loading" });
    try {
      const data = await createPrediction(slug);
      if (id !== latestRequest.current) return;
      setPrediction({ status: "success", data });
      history.reload();
      track.reload();
    } catch (error) {
      if (id === latestRequest.current) setPrediction({ status: "error", error: toApiError(error) });
    }
  }, [slug, history.reload, track.reload]);

  const symbols = coins.state.status === "success" ? coins.state.data.map((c) => symbolToSlug(c.symbol)) : [];
  const horizon = model.state.status === "success" ? model.state.data.horizon_candles : null;
  const base = slug.split("-")[0];

  return (
    <>
      <div className="page-head">
        <h1>{base} <span className="muted">{coinName(base)}</span></h1>
      </div>
      <Controls
        symbols={Array.from(new Set([slug, ...symbols]))}
        watchlist={watchlist}
        symbol={slug}
        onSymbolChange={(next) => navigate(`/forecast/${next}`)}
        onToggleWatch={toggleWatch}
        horizonCandles={horizon}
      />
      <div className="grid">
        <PredictionCard state={prediction} onPredict={run} symbolLabel={slugToSymbol(slug)} />
        <MarketCard state={market.state} onRetry={market.reload} />
        <HistoryTable state={history.state} onRetry={history.reload} />
        <TrackRecordCard state={track.state} onRetry={track.reload} />
      </div>
    </>
  );
}
