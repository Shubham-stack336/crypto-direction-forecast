import type { HistoryItem } from "./api/types";

export function formatPercent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatUtc(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${date.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

export function formatPrice(value: number): string {
  if (Math.abs(value) >= 100) return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return value.toLocaleString("en-US", { maximumSignificantDigits: 5, maximumFractionDigits: 10 });
}

export function formatCompact(value: number): string {
  return value.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 1 });
}

export function formatChange(percent: number): string {
  return `${percent > 0 ? "+" : ""}${percent.toFixed(2)}%`;
}

export function symbolToSlug(symbol: string): string {
  return symbol.replace("/", "-");
}

export function historyToCsv(items: HistoryItem[]): string {
  const head = "made_at_utc,symbol,forecast,prob_up,prob_sideways,prob_down,model";
  const rows = items.map((i) =>
    [i.prediction_time_utc, i.symbol, i.label, i.probabilities.UP, i.probabilities.SIDEWAYS, i.probabilities.DOWN, i.model_version].join(","),
  );
  return [head, ...rows].join("\n");
}

export function formatAge(minutes: number): string {
  if (minutes < 1) return "under a minute";
  if (minutes < 90) return `${Math.round(minutes)} min`;
  return `${(minutes / 60).toFixed(1)} h`;
}

export function slugToSymbol(slug: string): string {
  return slug.replace("-", "/");
}

export function symbolsFromModels(models: string[]): string[] {
  return [...new Set(models.map((entry) => entry.split(" ")[0].replace("/", "-")))].filter((slug) => slug !== "ALL-USDT");
}
