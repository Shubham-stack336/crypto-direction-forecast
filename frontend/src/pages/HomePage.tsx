import { Link } from "react-router";

import { getMarket } from "../api/client";
import { useAsync } from "../api/useAsync";
import { useAppData } from "../appData";
import { BigNumber } from "../components/BigNumber";
import { CoinCard } from "../components/CoinCard";
import { Icon } from "../components/Icon";
import { ErrorBox, Loading } from "../components/StateViews";
import { coinName } from "../coinNames";
import { formatChange, symbolToSlug } from "../format";

const CARDS = 8;

export function HomePage() {
  const { coins, watchlist } = useAppData();
  const list = coins.state.status === "success" ? coins.state.data : [];
  const slug = watchlist[0] ?? "BTC-USDT";
  const base = slug.split("-")[0];
  const coin = list.find((c) => symbolToSlug(c.symbol) === slug);
  const market = useAsync((signal) => getMarket(slug, signal), [slug]);
  const watched = list.filter((c) => watchlist.includes(symbolToSlug(c.symbol)));
  const cards = [...watched, ...list.filter((c) => !watched.includes(c))].slice(0, CARDS);

  return (
    <div className="home">
      <section className="home-hero" aria-labelledby="home-title">
        <div>
          <p className="wallet-line">
            <span className="muted">{coinName(base)}</span> ({base})
            {coin && <span className="pill">{formatChange(coin.change_pct)}</span>}
          </p>
          {coin && <BigNumber value={coin.last} />}
          {!coin && market.state.status === "success" && <BigNumber value={market.state.data.last_close} />}
          {!coin && market.state.status === "loading" && <p className="big-number dim">0.00</p>}
          {!coin && market.state.status === "error" && <ErrorBox error={market.state.error} onRetry={market.reload} />}
          <p className="muted">{coin ? "USDT, recent price" : "USDT at the last hourly close"}</p>
        </div>

        <div className="glass">
          <div className="glass-row">
            <h1 id="home-title">Up, down or sideways in the next three hours?</h1>
            {list.length > 0 && (
              <p className="count"><strong>{list.length}</strong><span>coins</span></p>
            )}
          </div>
          <hr />
          <Link className="slide" to={`/forecast/${slug}`}>
            <span className="knob" aria-hidden="true"><Icon name="arrow" /></span>
            <span className="slide-label">Forecast {base}</span>
            <span className="slide-dot" aria-hidden="true" />
          </Link>
        </div>
      </section>

      <section className="coin-field" aria-label="Most traded coins">
        {coins.state.status === "loading" && <Loading label="Loading coins…" />}
        {coins.state.status === "error" && <ErrorBox error={coins.state.error} onRetry={coins.reload} />}
        <div className="coin-grid">
          {cards.map((c) => <CoinCard key={c.symbol} coin={c} />)}
        </div>
        <div className="dock">
          <Link className="dock-main" to="/scanner"><Icon name="scan" /> Scan market</Link>
          <Link className="dock-side" to="/coins"><Icon name="dots" /> All coins</Link>
        </div>
      </section>
    </div>
  );
}
