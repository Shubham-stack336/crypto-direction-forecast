import { useEffect, useState } from "react";

export type Theme = "system" | "light" | "dark";
const KEY = "theme";

function read(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

const darkQuery = () => (typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null);

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(read);
  useEffect(() => {
    const query = darkQuery();
    const apply = () => {
      const dark = theme === "dark" || (theme === "system" && (query?.matches ?? false));
      document.documentElement.dataset.theme = dark ? "dark" : "light";
    };
    apply();
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      // storage blocked: the choice lasts until the page is closed
    }
    query?.addEventListener("change", apply);
    return () => query?.removeEventListener("change", apply);
  }, [theme]);
  return [theme, setTheme] as const;
}
