import { Link } from "react-router";

import { getMarket } from "../api/client";
import type { Coin } from "../api/types";
import { useAsync } from "../api/useAsync";
import { coinName } from "../coinNames";
import { formatChange, formatCompact, formatPrice, symbolToSlug } from "../format";
import { Sparkline } from "./Sparkline";

export function CoinCard({ coin }: { coin: Coin }) {
  const slug = symbolToSlug(coin.symbol);
  const base = coin.symbol.split("/")[0];
  const market = useAsync((signal) => getMarket(slug, signal), [slug]);
  return (
    <Link className="coin-card" to={`/forecast/${slug}`}>
      <span className="coin-top">
        <strong>{base}</strong>
        <span>{formatChange(coin.change_pct)}</span>
      </span>
      <span className="coin-name">{coinName(base)}</span>
      {market.state.status === "success" ? <Sparkline candles={market.state.data.candles} /> : <span className="spark" />}
      <span className="coin-bottom">
        <span className="glyph" aria-hidden="true">{base.slice(0, 1)}</span>
        <span className="coin-price">
          {formatPrice(coin.last)}
          <small>${formatCompact(coin.quote_volume)} volume</small>
        </span>
      </span>
    </Link>
  );
}
