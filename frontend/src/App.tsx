import { useCallback, useRef, useState } from "react";

import { createPrediction, getCoins, getHistory, getLive, getMarket, getModelStatus, getReady, getTrackRecord, toApiError } from "./api/client";
import { useAsync } from "./api/useAsync";
import { ApiStatus } from "./components/ApiStatus";
import { CoinExplorer } from "./components/CoinExplorer";
import { Controls } from "./components/Controls";
import { Disclaimer } from "./components/Disclaimer";
import { Hero } from "./components/Hero";
import { HistoryTable } from "./components/HistoryTable";
import { Logo } from "./components/Logo";
import { MarketCard } from "./components/MarketCard";
import { ModelCard } from "./components/ModelCard";
import { PredictionCard } from "./components/PredictionCard";
import type { PredictionState } from "./components/PredictionCard";
import { Scanner } from "./components/Scanner";
import { Spatial3DToken } from "./components/Spatial3DToken";
import { TrackRecordCard } from "./components/TrackRecordCard";
import { useWatchlist } from "./useWatchlist";
import { slugToSymbol, symbolsFromModels, symbolToSlug } from "./format";

const DEFAULT_SYMBOL = "BTC-USDT";

export default function App() {
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL);

  const live = useAsync((signal) => getLive(signal), []);
  const ready = useAsync((signal) => getReady(signal), []);
  const market = useAsync((signal) => getMarket(symbol, signal), [symbol]);
  const model = useAsync((signal) => getModelStatus(symbol, signal), [symbol]);
  const history = useAsync((signal) => getHistory(symbol, 20, 0, signal), [symbol]);

  const track = useAsync((signal) => getTrackRecord(symbol, signal), [symbol]);
  const coins = useAsync((signal) => getCoins(signal), []);
  const [watchlist, toggleWatch] = useWatchlist();

  const [prediction, setPrediction] = useState<PredictionState>({ status: "idle" });
  const latestRequest = useRef(0);

  const modelSymbols = ready.state.status === "success" ? symbolsFromModels(ready.state.data.models) : [DEFAULT_SYMBOL];
  const coinSymbols = coins.state.status === "success" ? coins.state.data.map((c) => symbolToSlug(c.symbol)) : modelSymbols;
  const options = Array.from(new Set([...coinSymbols, symbol]));

  const changeSymbol = useCallback((next: string) => {
    latestRequest.current += 1;
    setPrediction({ status: "idle" });
    setSymbol(next);
  }, []);

  const openCoin = useCallback(
    (next: string) => {
      changeSymbol(next);
      document.getElementById("dashboard")?.scrollIntoView({ behavior: "smooth" });
    },
    [changeSymbol],
  );

  const runPrediction = useCallback(async () => {
    const requestId = ++latestRequest.current;
    setPrediction({ status: "loading" });
    try {
      const data = await createPrediction(symbol);
      if (requestId !== latestRequest.current) return;
      setPrediction({ status: "success", data });
      history.reload();
      track.reload();
    } catch (error) {
      if (requestId !== latestRequest.current) return;
      setPrediction({ status: "error", error: toApiError(error) });
    }
  }, [symbol, history.reload, track.reload]);

  const horizon = model.state.status === "success" ? model.state.data.horizon_candles : null;

  return (
    <div className="spatial-root">
      <div className="spatial-canvas" aria-hidden="true">
        <div className="spatial-orb orb-1" />
        <div className="spatial-orb orb-2" />
        <div className="spatial-orb orb-3" />
      </div>

      <nav className="nav glass-panel" aria-label="Main">
        <a href="#top" aria-label="Crypto Direction, back to top">
          <Logo />
        </a>
        <div className="nav-links">
          <a href="#dashboard">Dashboard</a>
          <a href="#scanner">Scanner</a>
          <a href="#explorer">Coins</a>
        </div>
        <ApiStatus live={live.state} ready={ready.state} />
      </nav>

      <div className="page">
        <Hero coinCount={coins.state.status === "success" ? coins.state.data.length : null} />

        <Disclaimer />

        <main>
          <section id="dashboard" className="anchor">
            <div className="section-head">
              <Spatial3DToken symbol={symbol} />
              <h2>{slugToSymbol(symbol)}</h2>
            </div>
            <Controls
              symbols={options}
              watchlist={watchlist}
              symbol={symbol}
              onSymbolChange={changeSymbol}
              onToggleWatch={toggleWatch}
              horizonCandles={horizon}
            />
            <div className="grid">
              <PredictionCard state={prediction} onPredict={runPrediction} symbolLabel={slugToSymbol(symbol)} />
              <MarketCard state={market.state} onRetry={market.reload} />
              <HistoryTable state={history.state} onRetry={history.reload} />
              <TrackRecordCard state={track.state} onRetry={track.reload} />
              <div className="span-all">
                <ModelCard state={model.state} onRetry={model.reload} />
              </div>
            </div>
          </section>

          <div id="scanner" className="anchor">
            <Scanner onSelect={openCoin} />
          </div>
          <div id="explorer" className="anchor">
            <CoinExplorer
              state={coins.state}
              watchlist={watchlist}
              onRetry={coins.reload}
              onSelect={openCoin}
              onToggleWatch={toggleWatch}
            />
          </div>
        </main>

        <footer className="footer glass-panel">
          Forecasts come from statistical models trained on past hourly candles. They can be wrong, and past performance
          does not predict future results.
        </footer>
      </div>
    </div>
  );
}
