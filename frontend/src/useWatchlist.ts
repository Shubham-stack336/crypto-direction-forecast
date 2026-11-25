import { useCallback, useState } from "react";

const KEY = "watchlist";

function read(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

export function useWatchlist() {
  const [list, setList] = useState(read);
  const toggle = useCallback((slug: string) => {
    setList((current) => {
      const next = current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug];
      try {
        localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        // storage blocked: the list still works until the page is closed
      }
      return next;
    });
  }, []);
  return [list, toggle] as const;
}
