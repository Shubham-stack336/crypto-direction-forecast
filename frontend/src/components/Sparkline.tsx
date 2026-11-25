import type { Candle } from "../api/types";

const W = 200;
const H = 56;
const PAD = 7;

/** 24 hourly closes. Dotted line and filled dot: highest close. Open dot: latest close. */
export function Sparkline({ candles }: { candles: Candle[] }) {
  if (candles.length < 2) return <span className="spark" />;
  const closes = candles.map((c) => c.close);
  const low = Math.min(...closes);
  const high = Math.max(...closes);
  const x = (i: number) => PAD + (i / (closes.length - 1)) * (W - 2 * PAD);
  const y = (v: number) => H - PAD - ((v - low) / (high - low || 1)) * (H - 2 * PAD);
  const top = closes.indexOf(high);
  const last = closes.length - 1;
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Closing prices, last 24 hours">
      <line x1={PAD} x2={W - PAD} y1={y(high)} y2={y(high)} className="spark-high" />
      <polyline points={closes.map((v, i) => `${x(i)},${y(v)}`).join(" ")} className="spark-line" />
      <circle cx={x(last)} cy={y(closes[last])} r={3.5} className="spark-open" />
      <circle cx={x(top)} cy={y(high)} r={3.5} className="spark-dot" />
    </svg>
  );
}
