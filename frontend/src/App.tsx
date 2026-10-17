import { useCallback, useRef, useState } from "react";

import { createPrediction, getHistory, getLive, getMarket, getModelStatus, getReady, toApiError } from "./api/client";
import { useAsync } from "./api/useAsync";
import { ApiStatus } from "./components/ApiStatus";
import { Controls } from "./components/Controls";
import { Disclaimer } from "./components/Disclaimer";
import { HistoryTable } from "./components/HistoryTable";
import { MarketCard } from "./components/MarketCard";
import { ModelCard } from "./components/ModelCard";
import { PredictionCard } from "./components/PredictionCard";
import type { PredictionState } from "./components/PredictionCard";
import { slugToSymbol, symbolsFromModels } from "./format";

const DEFAULT_SYMBOL = "BTC-USDT";

export default function App() {
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL);

  const live = useAsync((signal) => getLive(signal), []);
  const ready = useAsync((signal) => getReady(signal), []);
  const market = useAsync((signal) => getMarket(symbol, signal), [symbol]);
  const model = useAsync((signal) => getModelStatus(symbol, signal), [symbol]);
  const history = useAsync((signal) => getHistory(symbol, 20, 0, signal), [symbol]);

  const [prediction, setPrediction] = useState<PredictionState>({ status: "idle" });
  const latestRequest = useRef(0);

  const symbols = ready.state.status === "success" ? symbolsFromModels(ready.state.data.models) : [DEFAULT_SYMBOL];
  const options = symbols.length > 0 ? symbols : [DEFAULT_SYMBOL];

  const changeSymbol = useCallback((next: string) => {
    latestRequest.current += 1;
    setPrediction({ status: "idle" });
    setSymbol(next);
  }, []);

  const runPrediction = useCallback(async () => {
    const requestId = ++latestRequest.current;
    setPrediction({ status: "loading" });
    try {
      const data = await createPrediction(symbol);
      if (requestId !== latestRequest.current) return;
      setPrediction({ status: "success", data });
      history.reload();
    } catch (error) {
      if (requestId !== latestRequest.current) return;
      setPrediction({ status: "error", error: toApiError(error) });
    }
  }, [symbol, history.reload]);

  const horizon = model.state.status === "success" ? model.state.data.horizon_candles : null;

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>Crypto Direction Forecast</h1>
          <p className="subtitle">Will the price go UP, DOWN or stay SIDEWAYS in the next few hours?</p>
        </div>
        <ApiStatus live={live.state} ready={ready.state} />
      </header>

      <Disclaimer />

      <Controls symbols={options} symbol={symbol} onSymbolChange={changeSymbol} horizonCandles={horizon} />

      <main className="grid">
        <PredictionCard state={prediction} onPredict={runPrediction} symbolLabel={slugToSymbol(symbol)} />
        <MarketCard state={market.state} onRetry={market.reload} />
        <ModelCard state={model.state} onRetry={model.reload} />
        <HistoryTable state={history.state} onRetry={history.reload} />
      </main>

      <footer className="footer">
        Forecasts come from a statistical model trained on past BTC/USDT hourly candles. They can be wrong, and past
        performance does not predict future results.
      </footer>
    </div>
  );
}
