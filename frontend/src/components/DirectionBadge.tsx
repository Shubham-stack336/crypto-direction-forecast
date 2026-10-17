import type { Direction } from "../api/types";

const SYMBOLS: Record<Direction, string> = { UP: "▲", DOWN: "▼", SIDEWAYS: "▬" };

export function DirectionBadge({ label }: { label: Direction }) {
  return (
    <span className={`badge badge-${label.toLowerCase()}`}>
      <span aria-hidden="true">{SYMBOLS[label]}</span> {label}
    </span>
  );
}
