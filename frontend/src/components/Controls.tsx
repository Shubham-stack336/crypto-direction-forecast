import { slugToSymbol } from "../format";

interface Props {
  symbols: string[];
  watchlist: string[];
  symbol: string;
  onSymbolChange: (symbol: string) => void;
  onToggleWatch: (symbol: string) => void;
  horizonCandles: number | null;
}

export function Controls({ symbols, watchlist, symbol, onSymbolChange, onToggleWatch, horizonCandles }: Props) {
  const watched = watchlist.includes(symbol);
  const option = (entry: string) => (
    <option key={entry} value={entry}>
      {slugToSymbol(entry)}
    </option>
  );
  const others = symbols.filter((entry) => !watchlist.includes(entry));
  return (
    <div className="controls">
      <label>
        Cryptocurrency
        <select value={symbol} onChange={(event) => onSymbolChange(event.target.value)}>
          {watchlist.length > 0 && <optgroup label="Watchlist">{watchlist.map(option)}</optgroup>}
          <optgroup label="All coins">{others.map(option)}</optgroup>
        </select>
      </label>
      <button type="button" className="button secondary" aria-pressed={watched} onClick={() => onToggleWatch(symbol)}>
        {watched ? "★ In watchlist" : "☆ Add to watchlist"}
      </button>
      <div className="control-fact">
        <span className="label">Forecast horizon</span>
        <span>{horizonCandles === null ? "…" : `${horizonCandles} candles (${horizonCandles} hours ahead)`}</span>
      </div>
    </div>
  );
}
