import { useRef, useState, type PointerEvent } from "react";

import { Icon } from "./Icon";

interface Props {
  label: string;
  busyLabel: string;
  busy: boolean;
  onConfirm: () => void;
}

/** Slide the knob, or just click / press Enter: both do the same. */
export function SlideButton({ label, busyLabel, busy, onConfirm }: Props) {
  const [offset, setOffset] = useState<number | null>(null);
  const drag = useRef({ x: 0, max: 0, moved: 0 });

  const down = (event: PointerEvent<HTMLButtonElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    drag.current = { x: event.clientX, max: Math.max(0, box.width - box.height), moved: 0 };
    setOffset(0);
  };
  const move = (event: PointerEvent<HTMLButtonElement>) => {
    if (offset === null) return;
    const moved = Math.min(drag.current.max, Math.max(0, event.clientX - drag.current.x));
    if (moved > 6) event.currentTarget.setPointerCapture?.(event.pointerId);
    drag.current.moved = moved;
    setOffset(moved);
  };
  const click = () => {
    const { moved, max } = drag.current;
    drag.current.moved = 0;
    if (moved > 6 && moved < max * 0.6) return; // let go too early: cancelled
    onConfirm();
  };

  return (
    <button
      type="button"
      className="slide"
      disabled={busy}
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={() => setOffset(null)}
      onPointerCancel={() => setOffset(null)}
      onPointerLeave={() => drag.current.moved <= 6 && setOffset(null)}
      onClick={click}
    >
      <span
        className="knob"
        style={offset === null ? undefined : { transform: `translateX(${offset}px)`, transition: "none" }}
        aria-hidden="true"
      >
        <Icon name="arrow" />
      </span>
      <span className="slide-label">{busy ? busyLabel : label}</span>
      <span className="slide-dot" aria-hidden="true" />
    </button>
  );
}
