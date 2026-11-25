import { useNavigate } from "react-router";

import { useAppData } from "../appData";
import { CoinExplorer } from "../components/CoinExplorer";

export default function CoinsPage() {
  const navigate = useNavigate();
  const { coins, watchlist, toggleWatch } = useAppData();
  return (
    <>
      <div className="page-head">
        <h1>Coins</h1>
        <p>Every USDT pair the models can forecast. Star one to put it first on your home page.</p>
      </div>
      <CoinExplorer
        state={coins.state}
        watchlist={watchlist}
        onRetry={coins.reload}
        onSelect={(slug) => navigate(`/forecast/${slug}`)}
        onToggleWatch={toggleWatch}
      />
    </>
  );
}
