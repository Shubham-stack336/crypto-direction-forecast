const PATHS = {
  grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  arrow: "M4 12h15M13 6l6 6-6 6",
  scan: "M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1",
  dots: "M5 8h.01M12 8h.01M19 8h.01M5 16h.01M12 16h.01M19 16h.01",
  chart: "M5 20V11M12 20V4M19 20v-6",
  person: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8M4 21c1-4 4-6 8-6s7 2 8 6",
  linkedin: "M5 10v10M5 5v.01M19 20v-6c0-2.5-1.5-4-3.5-4S12 11.5 12 14v6M12 20V10",
  moon: "M20 14A8 8 0 0 1 10 4a8 8 0 1 0 10 10",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6 19 19M19 5l-1.4 1.4M6.4 17.6 5 19",
  device: "M4 5h16v11H4zM9 20h6M12 16v4",
  compare: "M4 18 9 9l4 5 7-10M4 6l5 8 4-3 7 8",
  bell: "M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 21h4",
  check: "M4 12l5 5L20 6",
  github: "M9 20c-4 1-4-2-6-2M15 22v-4c0-1 0-2-1-2 3 0 6-1 6-6 0-1 0-2-1-4V3s-1 0-4 2a13 13 0 0 0-6 0C6 3 5 3 5 3v3c-1 2-1 3-1 4 0 5 3 6 6 6-1 0-1 1-1 2v4",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name }: { name: IconName }) {
  return (
    <svg className={`icon icon-${name}`} viewBox="0 0 24 24" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}
