import type { Direction } from "../api/types";

const SYMBOLS: Record<Direction, string> = { UP: "▲", DOWN: "▼", SIDEWAYS: "▬" };

export function DirectionBadge({ label }: { label: Direction }) {
  return (
    <span className={`badge badge-${label.toLowerCase()} spatial-badge`}>
      <span className="badge-glow" aria-hidden="true" />
      <span aria-hidden="true" className="badge-icon">{SYMBOLS[label]}</span> {label}
    </span>
  );
}
