import type { Candle } from "../api/types";
import { formatChange } from "../format";

const W = 760;
const H = 300;
const PAD = 34;

export interface Series {
  name: string;
  candles: Candle[];
}

/** Change since the start of the window, so coins with different prices share one scale. */
export function CompareChart({ series }: { series: Series[] }) {
  const lines = series.map((s) => ({ name: s.name, values: s.candles.map((c) => (c.close / s.candles[0].close - 1) * 100) }));
  const all = lines.flatMap((l) => l.values);
  const low = Math.min(0, ...all);
  const high = Math.max(0, ...all);
  const y = (v: number) => H - 14 - ((v - low) / (high - low || 1)) * (H - 28);
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Price change of each coin since the start of the period">
        {[low, 0, high].map((v, i) => (
          <g key={i}>
            <line className="chart-grid-line" x1={0} x2={W} y1={y(v)} y2={y(v)} />
            {(v !== 0 || i === 1) && <text className="chart-text" x={2} y={y(v) - 4}>{formatChange(v)}</text>}
          </g>
        ))}
        {lines.map((l, i) => (
          <polyline
            key={l.name}
            className={`line-${i + 1}`}
            points={l.values.map((v, n) => `${PAD + (n / Math.max(1, l.values.length - 1)) * (W - PAD * 2)},${y(v)}`).join(" ")}
          />
        ))}
      </svg>
      <ul className="legend">
        {lines.map((l, i) => (
          <li key={l.name}>
            <span className={`swatch swatch-${i + 1}`} aria-hidden="true" /> {l.name} {formatChange(l.values[l.values.length - 1])}
          </li>
        ))}
      </ul>
    </div>
  );
}
