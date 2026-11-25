import { useMemo, useState } from "react";

import type { AsyncState } from "../api/useAsync";
import type { Coin } from "../api/types";
import { formatChange, formatCompact, formatPrice, symbolToSlug } from "../format";
import { Card, Empty, ErrorBox, Loading } from "./StateViews";

const VIEWS = ["Most traded", "Gainers", "Losers", "Watchlist"] as const;
type View = (typeof VIEWS)[number];
const PAGE = 15;

interface Props {
  state: AsyncState<Coin[]>;
  watchlist: string[];
  onRetry: () => void;
  onSelect: (slug: string) => void;
  onToggleWatch: (slug: string) => void;
}

export function CoinExplorer({ state, watchlist, onRetry, onSelect, onToggleWatch }: Props) {
  const [query, setQuery] = useState("");
  const [view, setView] = useState<View>("Most traded");
  const [shown, setShown] = useState(PAGE);
  const coins = state.status === "success" ? state.data : null;

  const rows = useMemo(() => {
    const text = query.trim().toUpperCase();
    const list = (coins ?? []).filter(
      (c) => c.symbol.split("/")[0].includes(text) && (view !== "Watchlist" || watchlist.includes(symbolToSlug(c.symbol))),
    );
    if (view === "Gainers") list.sort((a, b) => b.change_pct - a.change_pct);
    if (view === "Losers") list.sort((a, b) => a.change_pct - b.change_pct);
    return list;
  }, [coins, query, view, watchlist]);

  return (
    <Card title="Coin explorer" id="explorer-title">
      {state.status === "loading" && <Loading label="Loading coins…" />}
      {state.status === "error" && <ErrorBox error={state.error} onRetry={onRetry} />}
      {coins && (
        <>
          <div className="toolbar">
            <input
              type="search"
              value={query}
              placeholder={`Search ${coins.length} coins`}
              aria-label="Search coins"
              onChange={(e) => {
                setQuery(e.target.value);
                setShown(PAGE);
              }}
            />
            <div className="segmented" role="group" aria-label="Sort coins">
              {VIEWS.map((v) => (
                <button
                  key={v}
                  type="button"
                  aria-pressed={view === v}
                  onClick={() => {
                    setView(v);
                    setShown(PAGE);
                  }}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
          {rows.length === 0 ? (
            <Empty>{view === "Watchlist" && !query ? "Star a coin to keep it here." : "No coin matches."}</Empty>
          ) : (
            <div className="table-wrap">
              <table>
                <caption className="sr-only">Coins that can be forecast</caption>
                <thead>
                  <tr>
                    <th scope="col"><span className="sr-only">Watchlist</span></th>
                    <th scope="col">Coin</th>
                    <th scope="col">Price (USDT)</th>
                    <th scope="col">24h</th>
                    <th scope="col">24h volume</th>
                    <th scope="col">Model</th>
                    <th scope="col"><span className="sr-only">Open</span></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, shown).map((c) => {
                    const slug = symbolToSlug(c.symbol);
                    const name = c.symbol.split("/")[0];
                    const watched = watchlist.includes(slug);
                    return (
                      <tr key={c.symbol}>
                        <td>
                          <button
                            type="button"
                            className="star"
                            aria-pressed={watched}
                            aria-label={`Watch ${name}`}
                            onClick={() => onToggleWatch(slug)}
                          >
                            {watched ? "★" : "☆"}
                          </button>
                        </td>
                        <th scope="row">{name}</th>
                        <td>{formatPrice(c.last)}</td>
                        <td className={c.change_pct >= 0 ? "pos" : "neg"}>{formatChange(c.change_pct)}</td>
                        <td>{formatCompact(c.quote_volume)}</td>
                        <td>{c.model === "dedicated" ? "Own" : "Universal"}</td>
                        <td>
                          <button type="button" className="link" aria-label={`Open ${name}`} onClick={() => onSelect(slug)}>
                            Open
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {rows.length > shown && (
            <button type="button" className="button secondary" onClick={() => setShown(shown + PAGE)}>
              Show more ({rows.length - shown} left)
            </button>
          )}
        </>
      )}
    </Card>
  );
}
