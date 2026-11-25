import { useState } from "react";

import type { Candle } from "../api/types";
import { formatPrice, formatUtc } from "../format";
import { Empty } from "./StateViews";

const W = 520;
const H = 190;
const PAD = 12;

export function SpatialChart({ candles }: { candles: Candle[] }) {
  const [mode, setMode] = useState<"Candles" | "Line">("Candles");
  const [active, setActive] = useState<number | null>(null);
  if (candles.length < 2) return <Empty>No candles to draw.</Empty>;

  const low = Math.min(...candles.map((c) => c.low));
  const high = Math.max(...candles.map((c) => c.high));
  const step = (W - PAD * 2) / candles.length;
  const x = (i: number) => PAD + step * (i + 0.5);
  const y = (p: number) => H - PAD - ((p - low) / (high - low || 1)) * (H - PAD * 2);
  const line = candles.map((c, i) => `${i ? "L" : "M"}${x(i)},${y(c.close)}`).join(" ");
  const shown = active === null ? null : candles[active];

  return (
    <div className="chart">
      <div className="chart-header">
        <span className="mono" aria-live="off">
          {shown
            ? `${formatUtc(shown.timestamp)}  O ${formatPrice(shown.open)}  H ${formatPrice(shown.high)}  L ${formatPrice(shown.low)}  C ${formatPrice(shown.close)}`
            : `Last ${candles.length} hours: ${formatPrice(low)} to ${formatPrice(high)}`}
        </span>
        <div className="segmented" role="group" aria-label="Chart type">
          {(["Candles", "Line"] as const).map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)}>
              {m}
            </button>
          ))}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Hourly price chart" onMouseLeave={() => setActive(null)}>
        {[0, 0.5, 1].map((f) => (
          <line key={f} className="chart-grid-line" x1={PAD} x2={W - PAD} y1={PAD + f * (H - PAD * 2)} y2={PAD + f * (H - PAD * 2)} />
        ))}
        {mode === "Line" && (
          <>
            <path className="chart-area" d={`${line} L${x(candles.length - 1)},${H - PAD} L${x(0)},${H - PAD} Z`} />
            <path className="chart-line" d={line} />
          </>
        )}
        {candles.map((c, i) => (
          <g key={c.timestamp} className={c.close >= c.open ? "candle-up" : "candle-down"} onMouseEnter={() => setActive(i)}>
            <rect className={active === i ? "chart-hit on" : "chart-hit"} x={x(i) - step / 2} y={0} width={step} height={H} />
            {mode === "Candles" && (
              <>
                <line x1={x(i)} x2={x(i)} y1={y(c.high)} y2={y(c.low)} />
                <rect
                  x={x(i) - step * 0.3}
                  width={step * 0.6}
                  y={Math.min(y(c.open), y(c.close))}
                  height={Math.max(1.5, Math.abs(y(c.open) - y(c.close)))}
                  rx={1.5}
                />
              </>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
