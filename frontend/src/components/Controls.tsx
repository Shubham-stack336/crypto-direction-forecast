import { slugToSymbol } from "../format";

interface Props {
  symbols: string[];
  symbol: string;
  onSymbolChange: (symbol: string) => void;
  horizonCandles: number | null;
}

export function Controls({ symbols, symbol, onSymbolChange, horizonCandles }: Props) {
  return (
    <div className="controls">
      <label>
        Cryptocurrency
        <select value={symbol} onChange={(event) => onSymbolChange(event.target.value)}>
          {symbols.map((entry) => (
            <option key={entry} value={entry}>
              {slugToSymbol(entry)}
            </option>
          ))}
        </select>
      </label>

      <label>
        Timeframe
        <select value="1h" disabled aria-describedby="timeframe-note">
          <option value="1h">1 hour candles</option>
        </select>
      </label>

      <div className="control-fact">
        <span className="label">Forecast horizon</span>
        <span>{horizonCandles === null ? "…" : `${horizonCandles} candles (${horizonCandles} hours ahead)`}</span>
      </div>
      <p id="timeframe-note" className="hint">
        Only models that have been trained and evaluated are offered.
      </p>
    </div>
  );
}
